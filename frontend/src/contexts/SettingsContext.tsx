import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

export type LLMProvider = 'anthropic' | 'google' | 'openai';
export type DataSource = 'live' | 'sandbox';

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
}

const DEFAULT_SETTINGS: StoredSettings = {
    markersLimit: 1000,
    llmProvider: 'openai',
    llmLimit: 10,
    agentTemperature: 0.3,
    dataSource: 'live',
    demoMode: false,
};

export const SettingsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [markersLimit, setMarkersLimitState] = useState(DEFAULT_SETTINGS.markersLimit);
    const [llmProvider, setLLMProviderState] = useState<LLMProvider>(DEFAULT_SETTINGS.llmProvider);
    const [llmLimit, setLLMLimitState] = useState(DEFAULT_SETTINGS.llmLimit);
    const [agentTemperature, setAgentTemperatureState] = useState(DEFAULT_SETTINGS.agentTemperature);
    const [dataSource, setDataSourceState] = useState<DataSource>(DEFAULT_SETTINGS.dataSource);
    const [demoMode, setDemoModeState] = useState(DEFAULT_SETTINGS.demoMode);

    // Load settings from localStorage on mount
    useEffect(() => {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed: Partial<StoredSettings> = JSON.parse(stored);
                if (parsed.markersLimit) setMarkersLimitState(parsed.markersLimit);
                if (parsed.llmProvider) setLLMProviderState(parsed.llmProvider);
                if (parsed.llmLimit) setLLMLimitState(parsed.llmLimit);
                if (parsed.agentTemperature !== undefined) setAgentTemperatureState(parsed.agentTemperature);
                if (parsed.dataSource) setDataSourceState(parsed.dataSource);
                if (parsed.demoMode !== undefined) setDemoModeState(parsed.demoMode);
            }
        } catch (e) {
            console.error('Failed to load settings', e);
        }
    }, []);

    // Save all settings to localStorage
    const saveSettings = (settings: Partial<StoredSettings>) => {
        try {
            const current: StoredSettings = {
                markersLimit,
                llmProvider,
                llmLimit,
                agentTemperature,
                dataSource,
                demoMode,
                ...settings,
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
        } catch (e) {
            console.error('Failed to save settings', e);
        }
    };

    const setMarkersLimit = (limit: number) => {
        setMarkersLimitState(limit);
        saveSettings({ markersLimit: limit });
    };

    const setLLMProvider = (provider: LLMProvider) => {
        setLLMProviderState(provider);
        saveSettings({ llmProvider: provider });
    };

    const setLLMLimit = (limit: number) => {
        setLLMLimitState(limit);
        saveSettings({ llmLimit: limit });
    };

    const setAgentTemperature = (temp: number) => {
        setAgentTemperatureState(temp);
        saveSettings({ agentTemperature: temp });
    };

    const setDataSource = (source: DataSource) => {
        setDataSourceState(source);
        saveSettings({ dataSource: source });
    };

    const setDemoMode = (enabled: boolean) => {
        setDemoModeState(enabled);
        saveSettings({ demoMode: enabled });
    };

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
        }}>
            {children}
        </SettingsContext.Provider>
    );
};

export const useSettings = (): SettingsContextType => {
    const context = useContext(SettingsContext);
    if (context === undefined) {
        throw new Error('useSettings must be used within a SettingsProvider');
    }
    return context;
};
