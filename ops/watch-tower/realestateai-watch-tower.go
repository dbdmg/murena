package main

import (
	"bufio"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"time"
)

var apiKey string
var commands []string
var logFile *os.File

const (
	lastCommitFile = ".last-deploy-commit"
	deployLogFile  = "cortina-watch-tower.log"
)

func loadConfig() error {
	// Leggi API key
	keyFile, err := os.ReadFile("config.txt")
	if err != nil {
		return fmt.Errorf("errore lettura config.txt: %v", err)
	}
	apiKey = strings.TrimSpace(string(keyFile))

	// Leggi comandi
	file, err := os.Open("commands.txt")
	if err != nil {
		return fmt.Errorf("errore lettura commands.txt: %v", err)
	}
	defer file.Close()

	commands = []string{}
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" && !strings.HasPrefix(line, "#") {
			commands = append(commands, line)
		}
	}

	if err := scanner.Err(); err != nil {
		return fmt.Errorf("errore parsing commands.txt: %v", err)
	}

	return nil
}

func initLogFile() error {
	var err error
	logFile, err = os.OpenFile(deployLogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("errore apertura log file: %v", err)
	}
	return nil
}

func writeLog(message string) {
	timestamp := time.Now().Format("2006-01-02 15:04:05")
	logLine := fmt.Sprintf("[%s] %s\n", timestamp, message)

	// Scrivi su file
	if logFile != nil {
		logFile.WriteString(logLine)
		logFile.Sync()
	}

	// Scrivi anche su console
	log.Print(message)
}

func getLastCommit() (string, error) {
	data, err := os.ReadFile(lastCommitFile)
	if err != nil {
		if os.IsNotExist(err) {
			return "", nil
		}
		return "", err
	}
	return strings.TrimSpace(string(data)), nil
}

func saveLastCommit(commit string) error {
	return os.WriteFile(lastCommitFile, []byte(commit), 0644)
}

func getRemoteCommit() (string, error) {
	// Fetch silenzioso per aggiornare i riferimenti remoti
	fetchCmd := exec.Command("git", "fetch", "origin", "main")
	// Usiamo l'opzione per non bloccare su SSH prompt
	fetchCmd.Env = append(os.Environ(), "GIT_SSH_COMMAND=ssh -o StrictHostKeyChecking=no")
	
	if err := fetchCmd.Run(); err != nil {
		return "", fmt.Errorf("git fetch fallito: %v", err)
	}

	// Ottieni l'hash del commit remoto
	cmd := exec.Command("git", "rev-parse", "origin/main")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

func executeCommands() error {
	wd, _ := os.Getwd()
	writeLog(fmt.Sprintf("Esecuzione comandi in: %s", wd))

	for _, cmd := range commands {
		writeLog(fmt.Sprintf("Eseguendo: %s", cmd))
		command := exec.Command("sh", "-c", cmd)
		out, err := command.CombinedOutput()

		if err != nil {
			return fmt.Errorf("comando fallito: %s - %v\nOutput: %s", cmd, err, string(out))
		}
	}
	return nil
}

func deployHandler(w http.ResponseWriter, r *http.Request) {
	// Verifica metodo
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Verifica API Key
	providedKey := r.Header.Get("X-API-Key")
	if providedKey != apiKey {
		writeLog("✗ Richiesta rifiutata - API Key invalida")
		http.Error(w, `{"error":"Unauthorized"}`, http.StatusUnauthorized)
		return
	}

	// 1. Ottieni il commit remoto attuale
	remoteCommit, err := getRemoteCommit()
	if err != nil {
		writeLog(fmt.Sprintf("✗ Errore nel recupero commit remoto: %v", err))
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprintf(w, `{"success":false,"error":"Errore controllo git"}`)
		return
	}

	// 2. Leggi l'ultimo commit su cui abbiamo fatto il deploy
	lastCommit, _ := getLastCommit()

	// 3. Verifica se è necessario il deploy
	if remoteCommit == lastCommit && lastCommit != "" {
		writeLog(fmt.Sprintf("→ Richiesta ricevuta - SKIP (già aggiornato al commit: %s)", remoteCommit[:8]))
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"success":true,"message":"Nessun cambiamento rilevato","commit":"%s"}`, remoteCommit)
		return
	}

	writeLog(fmt.Sprintf("→ Richiesta ricevuta - REBUILD (Nuovo commit: %s)", remoteCommit[:8]))

	// 4. Esegui i comandi (es. git pull, docker compose build, ecc.)
	if err := executeCommands(); err != nil {
		writeLog(fmt.Sprintf("✗ Deploy fallito: %v", err))
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprintf(w, `{"success":false,"error":"%s"}`, strings.ReplaceAll(err.Error(), "\"", "'"))
		return
	}

	// 5. Salva il nuovo commit come "eseguito"
	if err := saveLastCommit(remoteCommit); err != nil {
		writeLog(fmt.Sprintf("⚠ Deploy OK ma errore salvataggio stato commit: %v", err))
	}

	writeLog(fmt.Sprintf("✓ Deploy completato con successo (commit: %s)", remoteCommit[:8]))
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"success":true,"message":"Deploy completato","commit":"%s"}`, remoteCommit)
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"status":"ok","timestamp":"%s"}`, time.Now().Format(time.RFC3339))
}

func main() {
	// Carica configurazione (API key e comandi)
	if err := loadConfig(); err != nil {
		log.Fatalf("Errore caricamento config: %v", err)
	}

	// Inizializza il file di log
	if err := initLogFile(); err != nil {
		log.Fatalf("Errore inizializzazione log: %v", err)
	}
	defer logFile.Close()

	log.Printf("=== Deploy Server avviato ===")
	log.Printf("Comandi configurati: %d", len(commands))

	// Setup degli endpoint
	http.HandleFunc("/deploy", deployHandler)
	http.HandleFunc("/health", healthHandler)

	// Avvio del server
	port := "8891"
	host := "0.0.0.0" 
	writeLog(fmt.Sprintf("Server in ascolto su %s:%s", host, port))

	if err := http.ListenAndServe(host+":"+port, nil); err != nil {
		log.Fatalf("Errore critico del server: %v", err)
	}
}