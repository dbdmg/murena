import React, { createContext, useContext, useState, type ReactNode } from 'react';

export type LLMProvider = 'anthropic' | 'google' | 'openai';
export type DataSource = 'live' | 'sandbox';
export type Language = 'it' | 'en';

interface SettingsContextType {
    // Visualization
    markersLimit: number;
    setMarkersLimit: (limit: number) => void;
    // Intelligence
    llmProvider: LLMProvider;
    setLLMProvider: (provider: LLMProvider) => void;
    llmLimit: number;
    setLLMLimit: (limit: number) => void;
    agentTemperature: number;
    setAgentTemperature: (temp: number) => void;
    // Data
    dataSource: DataSource;
    setDataSource: (source: DataSource) => void;
    demoMode: boolean;
    setDemoMode: (enabled: boolean) => void;
    // Localization
    language: Language;
    setLanguage: (lang: Language) => void;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

const STORAGE_KEY = 'mef-settings';

interface StoredSettings {
    markersLimit: number;
    llmProvider: LLMProvider;
    llmLimit: number;
    agentTemperature: number;
    dataSource: DataSource;
    demoMode: boolean;
    language: Language;
}

const DEFAULT_SETTINGS: StoredSettings = {
    markersLimit: 1000,
    llmProvider: 'openai',
    llmLimit: 10,
    agentTemperature: 0.3,
    dataSource: 'live',
    demoMode: false,
    language: 'it',
};

const getStoredSettings = (): StoredSettings => {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            const parsed = JSON.parse(stored);
            return { ...DEFAULT_SETTINGS, ...parsed };
        }
    } catch (e) {
        console.error('Failed to load settings', e);
    }
    return DEFAULT_SETTINGS;
};

export const SettingsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    // Lazy initialization from localStorage
    const [settings, setSettings] = useState<StoredSettings>(() => getStoredSettings());

    const {
        markersLimit,
        llmProvider,
        llmLimit,
        agentTemperature,
        dataSource,
        demoMode,
        language
    } = settings;

    // Helper to update specific setting and save to local storage
    const updateSetting = <K extends keyof StoredSettings>(key: K, value: StoredSettings[K]) => {
        const newSettings = { ...settings, [key]: value };
        setSettings(newSettings);
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(newSettings));
        } catch (e) {
            console.error('Failed to save settings', e);
        }
    };

    const setMarkersLimit = (limit: number) => updateSetting('markersLimit', limit);
    const setLLMProvider = (provider: LLMProvider) => updateSetting('llmProvider', provider);
    const setLLMLimit = (limit: number) => updateSetting('llmLimit', limit);
    const setAgentTemperature = (temp: number) => updateSetting('agentTemperature', temp);
    const setDataSource = (source: DataSource) => updateSetting('dataSource', source);
    const setDemoMode = (enabled: boolean) => updateSetting('demoMode', enabled);
    const setLanguage = (lang: Language) => updateSetting('language', lang);

    return (
        <SettingsContext.Provider value={{
            markersLimit,
            setMarkersLimit,
            llmProvider,
            setLLMProvider,
            llmLimit,
            setLLMLimit,
            agentTemperature,
            setAgentTemperature,
            dataSource,
            setDataSource,
            demoMode,
            setDemoMode,
            language,
            setLanguage,
        }}>
            {children}
        </SettingsContext.Provider>
    );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useSettings = (): SettingsContextType => {
    const context = useContext(SettingsContext);
    if (context === undefined) {
        throw new Error('useSettings must be used within a SettingsProvider');
    }
    return context;
};
