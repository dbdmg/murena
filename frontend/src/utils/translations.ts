export const translations = {
    it: {
        // Layout / Navigation
        nav: {
            home: 'Home',
            map: 'Map',
            history: 'History',
            logs: 'Log attività',
            settings: 'Settings',
            about: 'About',
            logout: 'Logout',
            admin: 'Administrator',
        },
        // Search Page
        search: {
            placeholder: 'Descrivi l\'immobile o lo scenario che vuoi analizzare...',
            submit: 'Avvia',
            loading: 'Avvio...',
            suggested: 'Suggeriti:',
            recentHistory: 'Analisi recenti',
            noHistory: 'Nessuna analisi completata. Avvia la prima ricerca qui sopra.',
            found: 'trovate',
            demoMode: 'Modalita demo attiva',
            demoModeDesc: 'Uso dei dati sintetici locali',
            status: {
                completed: 'COMPLETED',
                failed: 'FAILED',
                processing: 'PROCESSING',
            },
            propertyFound: 'immobili trovati',
            error: 'Errore di analisi',
            processingDesc: 'Analisi in corso...',
        },
        // General
        common: {
            loading: 'Loading...',
        },
        // Login Page
        login: {
            welcome: 'Bentornato',
            subtitle: 'Accedi al sistema di analisi immobiliare',
            username: 'Username',
            usernamePlaceholder: 'Inserisci username',
            password: 'Password',
            forgotPassword: 'Password dimenticata?',
            submit: 'Login',
            orContinueWith: 'Oppure continua con',
            noAccount: 'Non hai un account?',
            contactAdmin: 'Contatta l\'amministratore',
            failed: 'Login non riuscito',
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
    },
    en: {
        // Layout / Navigation
        nav: {
            home: 'Home',
            map: 'Map',
            history: 'History',
            logs: 'Activity log',
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
