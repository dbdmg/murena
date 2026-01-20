import React, { useState } from 'react';
import {
    Settings,
    Map,
    Sliders,
    Wand2,
    RotateCcw,
    AlertTriangle,
    Check,
    Loader2,
    Cpu,
    Database,
    User,
    LogOut,
    Sparkles,
    Thermometer,
    Layers,
    Server,
} from 'lucide-react';
import { useSettings, type LLMProvider } from '../contexts/SettingsContext';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

// ============================================================================
// Constants
// ============================================================================

const LLM_PROVIDERS: { value: LLMProvider; label: string; description: string; icon: string; comingSoon?: boolean }[] = [
    { value: 'openai', label: 'OpenAI', description: 'GPT-5.2 / GPT-5-mini', icon: '🟢' },
    { value: 'google', label: 'Google Gemini', description: 'Gemini 3.0 Flash / 3.0 Pro', icon: '🔷', comingSoon: true },
    { value: 'anthropic', label: 'Anthropic', description: 'Claude 4.5 Sonnet / Opus', icon: '🟠', comingSoon: true },
];

const MARKERS_LIMIT_OPTIONS = [
    { value: 500, label: '500' },
    { value: 1000, label: '1.000' },
    { value: 2000, label: '2.000' },
    { value: 5000, label: '5.000' },
];

// ============================================================================
// Sub-components
// ============================================================================

const SectionCard: React.FC<{
    icon: React.ReactNode;
    title: string;
    iconColor?: string;
    children: React.ReactNode;
}> = ({ icon, title, iconColor = 'text-cyan-400', children }) => (
    <div className="bg-[#1a1d24]/60 border border-white/10 rounded-xl p-5 backdrop-blur-sm">
        <div className="flex items-center gap-2 mb-4">
            <span className={iconColor}>{icon}</span>
            <h2 className="font-semibold text-gray-200">{title}</h2>
        </div>
        {children}
    </div>
);

const SliderField: React.FC<{
    label: string;
    value: number;
    min: number;
    max: number;
    step?: number;
    onChange: (value: number) => void;
    helperText?: string;
    leftLabel?: string;
    rightLabel?: string;
    displayValue?: string;
}> = ({ label, value, min, max, step = 1, onChange, helperText, leftLabel, rightLabel, displayValue }) => (
    <div className="mb-5">
        <div className="flex items-center justify-between mb-2">
            <label className="text-sm text-gray-300">{label}</label>
            <span className="text-xs text-cyan-400 font-mono bg-cyan-500/10 px-2 py-0.5 rounded">
                {displayValue || value}
            </span>
        </div>
        {helperText && <p className="text-xs text-gray-500 mb-3">{helperText}</p>}
        <div className="relative">
            <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={value}
                onChange={(e) => onChange(Number(e.target.value))}
                className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none
                    [&::-webkit-slider-thumb]:w-4
                    [&::-webkit-slider-thumb]:h-4
                    [&::-webkit-slider-thumb]:rounded-full
                    [&::-webkit-slider-thumb]:bg-cyan-400
                    [&::-webkit-slider-thumb]:shadow-lg
                    [&::-webkit-slider-thumb]:shadow-cyan-500/30
                    [&::-webkit-slider-thumb]:cursor-pointer
                    [&::-webkit-slider-thumb]:transition-transform
                    [&::-webkit-slider-thumb]:hover:scale-110"
            />
            {(leftLabel || rightLabel) && (
                <div className="flex justify-between mt-1">
                    <span className="text-[10px] text-gray-500">{leftLabel}</span>
                    <span className="text-[10px] text-gray-500">{rightLabel}</span>
                </div>
            )}
        </div>
    </div>
);

// ============================================================================
// Main Component
// ============================================================================

export const SettingsPage: React.FC = () => {
    const {
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
    } = useSettings();

    const { user, logout } = useAuth();

    // Prompt reset state
    const [isResetting, setIsResetting] = useState(false);
    const [resetStatus, setResetStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [resetMessage, setResetMessage] = useState('');
    const [showConfirm, setShowConfirm] = useState(false);

    const handleResetPrompts = async () => {
        setIsResetting(true);
        setResetStatus('idle');
        setResetMessage('');

        try {
            const response = await apiClient.post('/prompts/reset');
            const data = response.data;

            setResetStatus('success');
            setResetMessage(data.message || 'Prompt ripristinati con successo!');
            setShowConfirm(false);

            setTimeout(() => {
                setResetStatus('idle');
                setResetMessage('');
            }, 5000);
        } catch (err: unknown) {
            setResetStatus('error');
            if (err && typeof err === 'object' && 'response' in err) {
                const axiosErr = err as { response?: { data?: { detail?: string } } };
                setResetMessage(axiosErr.response?.data?.detail || 'Errore durante il reset');
            } else if (err instanceof Error) {
                setResetMessage(err.message);
            } else {
                setResetMessage('Errore durante il reset');
            }
        } finally {
            setIsResetting(false);
        }
    };

    return (
        <div className="p-6 max-w-4xl mx-auto">
            {/* Header */}
            <div className="flex items-center gap-3 mb-8">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                    <Settings className="w-6 h-6 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-white">Impostazioni</h1>
                    <p className="text-sm text-gray-400">Configura ResPublica AI</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* ============================================================ */}
                {/* Column 1: Intelligence & AI Prompts */}
                {/* ============================================================ */}
                <div className="space-y-6">
                    {/* Intelligence Section */}
                    <SectionCard
                        icon={<Cpu className="w-4 h-4" />}
                        title="Intelligence"
                        iconColor="text-violet-400"
                    >
                        {/* Provider Selector */}
                        <div className="mb-5">
                            <div className="flex items-center gap-2 mb-2">
                                <Sparkles className="w-3.5 h-3.5 text-gray-500" />
                                <label className="text-sm text-gray-300">AI Provider</label>
                            </div>
                            <p className="text-xs text-gray-500 mb-3">
                                Seleziona il provider AI. Il modello specifico viene scelto automaticamente in base all'agente.
                            </p>
                            <div className="grid grid-cols-1 gap-2">
                                {LLM_PROVIDERS.map((provider) => (
                                    <button
                                        key={provider.value}
                                        onClick={() => !provider.comingSoon && setLLMProvider(provider.value)}
                                        disabled={provider.comingSoon}
                                        className={`
                                            flex items-center justify-between p-3 rounded-xl border transition-all text-left
                                            ${provider.comingSoon
                                                ? 'bg-white/[0.01] border-white/5 text-gray-500 cursor-not-allowed opacity-60'
                                                : llmProvider === provider.value
                                                    ? 'bg-violet-500/15 border-violet-500/50 text-violet-300'
                                                    : 'bg-white/[0.02] border-white/10 text-gray-400 hover:bg-white/5 hover:border-white/20'
                                            }
                                        `}
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="text-lg">{provider.icon}</span>
                                            <div>
                                                <div className="text-sm font-medium flex items-center gap-2">
                                                    {provider.label}
                                                    {provider.comingSoon && (
                                                        <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-500 font-semibold">
                                                            Coming Soon
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="text-xs opacity-60">{provider.description}</div>
                                            </div>
                                        </div>
                                        {llmProvider === provider.value && !provider.comingSoon && (
                                            <Check className="w-4 h-4 text-violet-400" />
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* LLM Limit Slider */}
                        <SliderField
                            label="Deep Analysis Batch Size"
                            value={llmLimit}
                            min={5}
                            max={50}
                            step={5}
                            onChange={setLLMLimit}
                            helperText="Numero di immobili da valutare in profondità. Valori più alti aumentano il tempo di analisi ma forniscono maggiore copertura."
                            leftLabel="5 (Veloce)"
                            rightLabel="50 (Completo)"
                        />

                        {/* Temperature Slider */}
                        <SliderField
                            label="Agent Temperature"
                            value={agentTemperature}
                            min={0}
                            max={1}
                            step={0.1}
                            onChange={setAgentTemperature}
                            displayValue={agentTemperature.toFixed(1)}
                            helperText="Controlla la creatività degli agenti AI. Valori bassi = risposte più precise, valori alti = risposte più creative."
                            leftLabel="Analitico"
                            rightLabel="Creativo"
                        />

                        {/* Info */}
                        <div className="p-3 bg-violet-500/10 border border-violet-500/20 rounded-lg">
                            <p className="text-xs text-violet-400">
                                <Thermometer className="w-3 h-3 inline mr-1" />
                                Le modifiche alla configurazione AI saranno applicate alla prossima analisi.
                            </p>
                        </div>
                    </SectionCard>

                    {/* AI Prompts Section */}
                    <SectionCard
                        icon={<Wand2 className="w-4 h-4" />}
                        title="Prompt AI"
                        iconColor="text-amber-400"
                    >
                        <p className="text-sm text-gray-400 mb-4">
                            I prompt definiscono come gli agenti AI analizzano e valutano gli immobili.
                            Puoi modificarli tramite l'Agent Tuner sulla mappa.
                        </p>

                        {/* Reset Status */}
                        {resetStatus !== 'idle' && (
                            <div
                                className={`mb-4 p-3 rounded-lg border ${resetStatus === 'success'
                                    ? 'bg-emerald-500/10 border-emerald-500/20'
                                    : 'bg-red-500/10 border-red-500/20'
                                    }`}
                            >
                                <div className="flex items-center gap-2">
                                    {resetStatus === 'success' ? (
                                        <Check className="w-4 h-4 text-emerald-400" />
                                    ) : (
                                        <AlertTriangle className="w-4 h-4 text-red-400" />
                                    )}
                                    <p className={`text-sm ${resetStatus === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>
                                        {resetMessage}
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Reset Confirmation */}
                        {showConfirm ? (
                            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
                                <div className="flex items-start gap-3 mb-4">
                                    <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                                    <div>
                                        <h3 className="text-sm font-semibold text-red-400 mb-1">Conferma Reset</h3>
                                        <p className="text-xs text-gray-400">
                                            Tutti i prompt AI verranno ripristinati ai valori di default.
                                            Le personalizzazioni andranno perse.
                                        </p>
                                    </div>
                                </div>
                                <div className="flex gap-2 justify-end">
                                    <button
                                        onClick={() => setShowConfirm(false)}
                                        disabled={isResetting}
                                        className="px-4 py-2 text-sm font-medium text-gray-400 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors"
                                    >
                                        Annulla
                                    </button>
                                    <button
                                        onClick={handleResetPrompts}
                                        disabled={isResetting}
                                        className="px-4 py-2 text-sm font-medium text-white bg-red-500/80 border border-red-500/50 rounded-lg hover:bg-red-500 transition-colors flex items-center gap-2"
                                    >
                                        {isResetting ? (
                                            <>
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                Ripristino...
                                            </>
                                        ) : (
                                            <>
                                                <RotateCcw className="w-4 h-4" />
                                                Conferma
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <button
                                onClick={() => setShowConfirm(true)}
                                className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-300 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 hover:text-white transition-colors"
                            >
                                <RotateCcw className="w-4 h-4" />
                                Ripristina Prompt di Default
                            </button>
                        )}
                    </SectionCard>
                </div>

                {/* ============================================================ */}
                {/* Column 2: Visualization, Data & Account */}
                {/* ============================================================ */}
                <div className="space-y-6">
                    {/* Visualization Section */}
                    <SectionCard
                        icon={<Map className="w-4 h-4" />}
                        title="Visualizzazione"
                        iconColor="text-cyan-400"
                    >
                        {/* Viewport Object Limit */}
                        <div className="mb-4">
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <Layers className="w-3.5 h-3.5 text-gray-500" />
                                    <label className="text-sm text-gray-300">Viewport Object Limit</label>
                                </div>
                                <span className="text-xs text-cyan-400 font-mono bg-cyan-500/10 px-2 py-0.5 rounded">
                                    {markersLimit.toLocaleString()}
                                </span>
                            </div>
                            <p className="text-xs text-gray-500 mb-3">
                                Numero massimo di immobili visualizzati sulla mappa.
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {MARKERS_LIMIT_OPTIONS.map((option) => (
                                    <button
                                        key={option.value}
                                        onClick={() => setMarkersLimit(option.value)}
                                        className={`
                                            px-4 py-2 rounded-xl text-sm font-medium transition-all
                                            ${markersLimit === option.value
                                                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                                                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
                                            }
                                        `}
                                    >
                                        {option.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Warning */}
                        <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                            <p className="text-xs text-amber-400">
                                ⚠️ Un numero elevato di marker potrebbe rallentare la mappa.
                            </p>
                        </div>
                    </SectionCard>

                    {/* Data Source Section */}
                    <SectionCard
                        icon={<Database className="w-4 h-4" />}
                        title="Sorgente Dati"
                        iconColor="text-emerald-400"
                    >
                        <p className="text-xs text-gray-500 mb-4">
                            Seleziona la sorgente dati per le analisi.
                        </p>

                        <div className="grid grid-cols-2 gap-3">
                            <button
                                onClick={() => setDataSource('live')}
                                className={`
                                    p-4 rounded-xl border transition-all text-left
                                    ${dataSource === 'live'
                                        ? 'bg-emerald-500/15 border-emerald-500/50'
                                        : 'bg-white/[0.02] border-white/10 hover:bg-white/5'
                                    }
                                `}
                            >
                                <Server className={`w-5 h-5 mb-2 ${dataSource === 'live' ? 'text-emerald-400' : 'text-gray-500'}`} />
                                <div className={`text-sm font-medium ${dataSource === 'live' ? 'text-emerald-300' : 'text-gray-400'}`}>
                                    Live
                                </div>
                                <div className="text-xs text-gray-500 mt-1">Dataset completo</div>
                            </button>

                            <button
                                onClick={() => setDataSource('sandbox')}
                                className={`
                                    p-4 rounded-xl border transition-all text-left
                                    ${dataSource === 'sandbox'
                                        ? 'bg-amber-500/15 border-amber-500/50'
                                        : 'bg-white/[0.02] border-white/10 hover:bg-white/5'
                                    }
                                `}
                            >
                                <Sliders className={`w-5 h-5 mb-2 ${dataSource === 'sandbox' ? 'text-amber-400' : 'text-gray-500'}`} />
                                <div className={`text-sm font-medium ${dataSource === 'sandbox' ? 'text-amber-300' : 'text-gray-400'}`}>
                                    Sandbox
                                </div>
                                <div className="text-xs text-gray-500 mt-1">Dati demo</div>
                            </button>
                        </div>

                        {dataSource === 'sandbox' && (
                            <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                                <p className="text-xs text-amber-400">
                                    🧪 Modalità Sandbox attiva. I dati mostrati sono solo dimostrativi.
                                </p>
                            </div>
                        )}
                    </SectionCard>

                    {/* Account Section */}
                    <SectionCard
                        icon={<User className="w-4 h-4" />}
                        title="Account"
                        iconColor="text-blue-400"
                    >
                        {user ? (
                            <>
                                {/* Profile Card */}
                                <div className="flex items-center gap-4 p-4 bg-gradient-to-r from-white/[0.03] to-transparent border border-white/10 rounded-xl mb-4">
                                    <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-blue-500/20">
                                        {user.username?.charAt(0).toUpperCase() || 'U'}
                                    </div>
                                    <div className="flex-1">
                                        <div className="text-lg font-semibold text-white">{user.username}</div>
                                        <div className="text-sm text-gray-400">{user.email}</div>
                                        <div className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 bg-blue-500/20 border border-blue-500/30 rounded-full">
                                            <span className="text-xs text-blue-400 font-medium">Analista</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Sign Out Button */}
                                <button
                                    onClick={logout}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl hover:bg-red-500/20 hover:border-red-500/40 transition-all"
                                >
                                    <LogOut className="w-4 h-4" />
                                    Disconnetti
                                </button>
                            </>
                        ) : (
                            <div className="text-center py-8 text-gray-500">
                                <User className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                <p className="text-sm">Nessun utente connesso</p>
                            </div>
                        )}
                    </SectionCard>
                </div>
            </div>

            {/* Footer */}
            <div className="mt-8 pt-6 border-t border-white/10 text-center">
                <p className="text-xs text-gray-500">
                    ResPublica AI v0.9.2 Alpha • Le modifiche vengono salvate automaticamente
                </p>
            </div>
        </div>
    );
};
