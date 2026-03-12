export const translations = {
    it: {
        // Layout / Navigation
        nav: {
            home: 'Home',
            map: 'Mappa',
            history: 'Cronologia',
            settings: 'Impostazioni',
            about: 'Informazioni',
            logout: 'Disconnetti',
            admin: 'Amministratore',
        },
        // Search Page
        search: {
            placeholder: 'Descrivi cosa stai cercando...',
            submit: 'Inizializza',
            loading: 'Avvio...',
            suggested: 'Suggeriti:',
            recentHistory: 'Approfondimenti Recenti',
            noHistory: 'Nessuna analisi completata. Inizia la tua prima ricerca sopra!',
            found: 'trovati',
            demoMode: 'Modalità Demo Attiva',
            demoModeDesc: 'Utilizzo risultati pre-calcolati (nessun consumo token)',
            status: {
                completed: 'COMPLETATO',
                failed: 'FALLITO',
                processing: 'IN CORSO',
            },
            propertyFound: 'immobili trovati',
            error: "Errore durante l'analisi",
            processingDesc: 'Analisi in corso...',
        },
        // General
        common: {
            loading: 'Caricamento...',
        },
        // Login Page
        login: {
            welcome: 'Bentornato',
            subtitle: 'Accedi al Sistema Analitico Immobiliare',
            username: 'Nome utente',
            usernamePlaceholder: 'Inserisci il tuo nome utente',
            password: 'Password',
            forgotPassword: 'Password dimenticata?',
            submit: 'Accedi',
            orContinueWith: 'O continua con',
            noAccount: 'Non hai un account?',
            contactAdmin: 'Contatta l\'amministratore',
            failed: 'Accesso fallito',
        },
        // Processing Page
        processing: {
            sessionTitle: 'Sessione di ricerca AI',
            complete: 'Analisi completata',
            processing: 'Elaborazione richiesta...',
            foundStats: 'Trovati {count} immobili corrispondenti ai criteri',
            newSearch: 'Nuova ricerca',
            viewMap: 'Visualizza mappa interattiva',
            stopAnalysis: 'Interrompi analisi',
        }
    },
    en: {
        // Layout / Navigation
        nav: {
            home: 'Home',
            map: 'Map',
            history: 'History',
            settings: 'Settings',
            about: 'About',
            logout: 'Logout',
            admin: 'Administrator',
        },
        // Search Page
        search: {
            placeholder: 'Describe what you are looking for...',
            submit: 'Initialize',
            loading: 'Starting...',
            suggested: 'Suggested:',
            recentHistory: 'Recent Insights',
            noHistory: 'No completed analysis. Start your first search above!',
            found: 'found',
            demoMode: 'Demo Mode Active',
            demoModeDesc: 'Using pre-calculated results (no token consumption)',
            status: {
                completed: 'COMPLETED',
                failed: 'FAILED',
                processing: 'PROCESSING',
            },
            propertyFound: 'properties found',
            error: 'Analysis error',
            processingDesc: 'Analysis in progress...',
        },
        // General
        common: {
            loading: 'Loading...',
        },
        // Login Page
        login: {
            welcome: 'Welcome Back',
            subtitle: 'Access the Real Estate Analytical System',
            username: 'Username',
            usernamePlaceholder: 'Enter your username',
            password: 'Password',
            forgotPassword: 'Forgot password?',
            submit: 'Login',
            orContinueWith: 'Or continue with',
            noAccount: 'Don\'t have an account?',
            contactAdmin: 'Contact administrator',
            failed: 'Login failed',
        },
        // Processing Page
        processing: {
            sessionTitle: 'AI Search Session',
            complete: 'Analysis completed',
            processing: 'Processing request...',
            foundStats: 'Found {count} matching properties',
            newSearch: 'New search',
            viewMap: 'View interactive map',
            stopAnalysis: 'Stop analysis',
        }
    }
};

export type TranslationKeys = typeof translations.it;
