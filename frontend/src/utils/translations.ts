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
