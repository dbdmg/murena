/**
 * AgentRefinementHUD - Expert Validation Modal
 *
 * A large modal that allows real-time editing of AI prompts
 * and re-execution of analysis runs.
 *
 * The Validation Loop:
 * 1. Visualize - User sees results on map (Tier 2/3)
 * 2. Critique - User notices issues with AI selections
 * 3. Refine - User edits the System Prompt or Query
 * 4. Simulate - User clicks Re-Run
 * 5. Verify - Map updates with new results
 * 6. Commit - If satisfied, save as default
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    X,
    Play,
    Save,
    RotateCcw,
    ChevronDown,
    ChevronUp,
    Hash,
    AlertCircle,
    Check,
    Loader2,
    Sparkles,
    Code2,
    MessageSquare,
    Wand2,
} from 'lucide-react';
import { analysisApi } from '../../api/endpoints/analysis';
import apiClient from '../../api/client';
import type { AgentStep } from '../../api/types';

// ============================================================================
// Constants
// ============================================================================

/**
 * Maps step keys from the analysis run to prompt config agent names.
 * Step keys come from gemini_responses, agent names are used in prompt_config.md
 */
const STEP_TO_AGENT_MAP: Record<string, string> = {
    'evaluation': 'evaluation_agent',
    'location_extraction': 'location_agent',
    'typology_extraction': 'typology_agent',

    'use_case_generation': 'use_case_agent',
    'sql_generation': 'sql_agent',
    'ape_analysis': 'ape_agent',
    'poi_analysis': 'poi_agent',
    'broker_review': 'broker_agent',
    'map_assistant': 'map_assistant',
};

/**
 * Get the prompt config agent name for a given step key
 */
const getAgentNameForStep = (stepKey: string): string => {
    return STEP_TO_AGENT_MAP[stepKey] || stepKey;
};

// ============================================================================
// Types
// ============================================================================

interface AgentRefinementHUDProps {
    /** Current active run ID */
    activeRunId: string | null;
    /** The original query used */
    currentQuery: string;
    /** Callback to switch to a new run */
    onRunSwitch: (runId: string) => void;
    /** Whether the HUD is open */
    isOpen: boolean;
    /** Toggle HUD open/close */
    onToggle: () => void;
    /** Optional className for the trigger */
    className?: string;
}

// ============================================================================
// Trigger Button Component (similar to MapLegend style)
// ============================================================================

interface TriggerButtonProps {
    isOpen: boolean;
    onClick: () => void;
    hasActiveRun: boolean;
}

const TriggerButton: React.FC<TriggerButtonProps> = ({ isOpen, onClick, hasActiveRun }) => {
    const [isHovered, setIsHovered] = useState(false);

    return (
        <div
            className="relative"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            <div className="bg-[#0a0d12]/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-xl shadow-black/30 p-2 flex items-center gap-2">
                <div className={`px-2 ${isHovered || isOpen ? 'text-violet-400' : 'text-gray-500'}`}>
                    <Wand2 className="w-4 h-4" />
                </div>

                <button
                    onClick={onClick}
                    className={`
                        flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
                        transition-all duration-200 border whitespace-nowrap
                        ${isOpen || isHovered
                            ? 'bg-violet-500/20 text-violet-400 border-violet-500/50'
                            : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20 hover:bg-white/10'
                        }
                    `}
                >
                    <span className="font-medium">Agent Tuner</span>
                    {hasActiveRun && (
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    )}
                </button>
            </div>
        </div>
    );
};

// ============================================================================
// PromptEditor Component - Large and Elegant
// ============================================================================

interface PromptEditorProps {
    value: string;
    onChange: (value: string) => void;
    label: string;
    agentLabel?: string;
    readOnly?: boolean;
    placeholder?: string;
}

const PromptEditor: React.FC<PromptEditorProps> = ({
    value,
    onChange,
    label,
    agentLabel,
    readOnly = false,
    placeholder,
}) => {
    // Count lines for line numbers
    const lines = value.split('\n');
    const lineCount = lines.length;

    return (
        <div className="flex-1 flex flex-col min-h-0">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-linear-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/30 flex items-center justify-center">
                        <Code2 className="w-4 h-4 text-violet-400" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-white">{label}</h3>
                        {agentLabel && (
                            <p className="text-xs text-gray-500">{agentLabel}</p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                    <span>{lineCount} righe</span>
                    <span>•</span>
                    <span>{value.length} caratteri</span>
                </div>
            </div>

            {/* Editor Container */}
            <div className="flex-1 relative rounded-2xl overflow-hidden border border-white/10 bg-[#080a0e]">
                {/* Gradient border effect */}
                <div className="absolute inset-0 rounded-2xl bg-linear-to-br from-violet-500/10 via-transparent to-cyan-500/10 pointer-events-none" />

                {/* Editor with line numbers feel */}
                <div className="absolute inset-0 flex">
                    {/* Line numbers gutter */}
                    <div className="w-12 bg-white/2 border-r border-white/5 py-4 select-none overflow-hidden">
                        <div className="flex flex-col items-end pr-3 font-mono text-[11px] text-gray-600 leading-6">
                            {Array.from({ length: Math.max(lineCount, 20) }, (_, i) => (
                                <span key={i + 1}>{i + 1}</span>
                            ))}
                        </div>
                    </div>

                    {/* Textarea */}
                    <textarea
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        readOnly={readOnly}
                        placeholder={placeholder}
                        spellCheck={false}
                        className={`
                            flex-1 p-4 bg-transparent
                            font-mono text-sm text-gray-200 leading-6
                            placeholder:text-gray-700
                            focus:outline-none
                            resize-none
                            whitespace-pre-wrap wrap-break-word
                            overflow-y-auto overflow-x-hidden
                            scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10
                            ${readOnly ? 'opacity-60 cursor-not-allowed' : ''}
                        `}
                        style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Monaco', monospace" }}
                    />
                </div>

                {/* Bottom fade */}
                <div className="absolute bottom-0 left-0 right-0 h-8 bg-linear-to-t from-[#080a0e] to-transparent pointer-events-none" />
            </div>
        </div>
    );
};

// ============================================================================
// Variable Context Display
// ============================================================================

interface VariableContextProps {
    variables: Record<string, string>;
}

const VariableContext: React.FC<VariableContextProps> = ({ variables }) => {
    const [isExpanded, setIsExpanded] = useState(true);

    if (Object.keys(variables).length === 0) return null;

    return (
        <div className="space-y-2">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-300 transition-colors"
            >
                <MessageSquare className="w-3.5 h-3.5" />
                Variabili di Contesto
                {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>

            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                    >
                        <div className="p-4 rounded-xl bg-[#080a0e] border border-white/5 space-y-2">
                            {Object.entries(variables).map(([key, value]) => (
                                <div key={key} className="flex items-start gap-3">
                                    <code className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 text-xs font-mono">
                                        {`{{${key}}}`}
                                    </code>
                                    <span className="text-gray-400 text-sm font-mono break-all flex-1">
                                        "{value.length > 100 ? value.slice(0, 100) + '...' : value}"
                                    </span>
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

// ============================================================================
// Main AgentRefinementHUD Component
// ============================================================================

export const AgentRefinementHUD: React.FC<AgentRefinementHUDProps> = ({
    activeRunId,
    currentQuery,
    onRunSwitch,
    isOpen,
    onToggle,
    className = '',
}) => {
    // State
    const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
    const [selectedAgent, setSelectedAgent] = useState<string>('evaluation');
    const [editedSystemPrompt, setEditedSystemPrompt] = useState<string>('');
    const [editedUserPrompt, setEditedUserPrompt] = useState<string>('');
    const [originalSystemPrompt, setOriginalSystemPrompt] = useState<string>('');
    const [originalUserPrompt, setOriginalUserPrompt] = useState<string>('');
    const [activeTab, setActiveTab] = useState<'system' | 'user'>('system');
    const [isLoading, setIsLoading] = useState(false);
    const [isSimulating, setIsSimulating] = useState(false);
    const [simulationProgress, setSimulationProgress] = useState<string>('');
    const [simulatedRunId, setSimulatedRunId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [isResettingToDefault, setIsResettingToDefault] = useState(false);

    // Derived state
    const hasChanges = editedSystemPrompt !== originalSystemPrompt || editedUserPrompt !== originalUserPrompt;
    const canSave = simulatedRunId !== null;

    // Load agent steps when run changes
    useEffect(() => {
        if (!activeRunId || !isOpen) return;

        const loadSteps = async () => {
            setIsLoading(true);
            setError(null);
            try {
                // Load agent steps from run (for metadata/structure)
                const steps = await analysisApi.getAgentSteps(activeRunId, {
                    include_prompt: true,
                    include_raw: true,
                });
                setAgentSteps(steps);

                // Load CURRENT prompts from config file (not from run snapshot)
                // This ensures we always see the latest saved prompts
                const agentName = getAgentNameForStep(selectedAgent);
                try {
                    const [systemResp, userResp] = await Promise.all([
                        apiClient.get(`/prompts/overrides/${agentName}/system`),
                        apiClient.get(`/prompts/overrides/${agentName}/user`),
                    ]);

                    const systemPrompt = systemResp.data?.text || '';
                    const userPrompt = userResp.data?.text || '';
                    setOriginalSystemPrompt(systemPrompt);
                    setOriginalUserPrompt(userPrompt);
                    setEditedSystemPrompt(systemPrompt);
                    setEditedUserPrompt(userPrompt);
                } catch (promptErr) {
                    // Fallback to run prompts if config fetch fails
                    console.warn('Failed to load prompts from config, using run snapshot:', promptErr);
                    const selectedStep = steps.find((s) => s.key === selectedAgent);
                    if (selectedStep?.prompt) {
                        const systemPrompt = selectedStep.prompt.system || '';
                        const userPrompt = selectedStep.prompt.user || '';
                        setOriginalSystemPrompt(systemPrompt);
                        setOriginalUserPrompt(userPrompt);
                        setEditedSystemPrompt(systemPrompt);
                        setEditedUserPrompt(userPrompt);
                    }
                }
            } catch (err) {
                setError('Impossibile caricare i dati dell\'agent');
                console.error('Failed to load agent steps:', err);
            } finally {
                setIsLoading(false);
            }
        };

        loadSteps();
    }, [activeRunId, isOpen, selectedAgent]);

    // Handle agent selection change - load prompts from config file
    const handleAgentChange = useCallback(async (agentKey: string) => {
        setSelectedAgent(agentKey);
        setSimulatedRunId(null);

        // Load prompts from config file for the new agent
        const agentName = getAgentNameForStep(agentKey);
        try {
            const [systemResp, userResp] = await Promise.all([
                apiClient.get(`/prompts/overrides/${agentName}/system`),
                apiClient.get(`/prompts/overrides/${agentName}/user`),
            ]);

            const systemPrompt = systemResp.data?.text || '';
            const userPrompt = userResp.data?.text || '';
            setOriginalSystemPrompt(systemPrompt);
            setOriginalUserPrompt(userPrompt);
            setEditedSystemPrompt(systemPrompt);
            setEditedUserPrompt(userPrompt);
        } catch {
            // Fallback to step prompts if config fails
            const step = agentSteps.find((s) => s.key === agentKey);
            if (step?.prompt) {
                const systemPrompt = step.prompt.system || '';
                const userPrompt = step.prompt.user || '';
                setOriginalSystemPrompt(systemPrompt);
                setOriginalUserPrompt(userPrompt);
                setEditedSystemPrompt(systemPrompt);
                setEditedUserPrompt(userPrompt);
            } else {
                setOriginalSystemPrompt('');
                setOriginalUserPrompt('');
                setEditedSystemPrompt('');
                setEditedUserPrompt('');
            }
        }
    }, [agentSteps]);

    // Handle Re-Run / Simulate
    const handleReRun = useCallback(async () => {


        if (!currentQuery) {
            setError('Query non disponibile. Esegui prima una ricerca dalla mappa.');
            return;
        }

        setIsSimulating(true);
        setSimulationProgress('Salvataggio prompt...');
        setError(null);
        setSuccessMessage(null);

        const agentName = getAgentNameForStep(selectedAgent);


        try {
            // Step 1: Save the modified prompts to backend BEFORE running analysis
            if (hasChanges) {
                try {

                    await apiClient.put(`/prompts/overrides/${agentName}/system`, { text: editedSystemPrompt });
                    await apiClient.put(`/prompts/overrides/${agentName}/user`, { text: editedUserPrompt });
                    setSimulationProgress('Prompt salvati. Avvio analisi...');

                    // Update original prompts since we saved them
                    setOriginalSystemPrompt(editedSystemPrompt);
                    setOriginalUserPrompt(editedUserPrompt);
                } catch (saveErr) {
                    console.error('Failed to save prompts:', saveErr);
                    setError('Impossibile salvare i prompt modificati');
                    setIsSimulating(false);
                    setSimulationProgress('');
                    return;
                }
            } else {
                setSimulationProgress('Avvio analisi...');
            }

            // Step 2: Start analysis
            const response = await analysisApi.startAnalysis({
                query: currentQuery,
                analysis_mode: 'agent',
            });

            let attempts = 0;
            const maxAttempts = 120; // 2 minutes max

            while (attempts < maxAttempts) {
                await new Promise((resolve) => setTimeout(resolve, 1000));
                const results = await analysisApi.getResults(response.run_id);

                // Update progress based on status
                if (results.status === 'processing') {
                    const elapsed = attempts + 1;
                    setSimulationProgress(`Elaborazione in corso... (${elapsed}s)`);
                } else if (results.status === 'completed') {
                    setSimulatedRunId(response.run_id);
                    onRunSwitch(response.run_id);
                    setSuccessMessage('Simulazione completata! La mappa è stata aggiornata.');
                    setSimulationProgress('');
                    break;
                } else if (results.status === 'failed') {
                    const errorMessage = (results as { error?: string }).error || 'Errore sconosciuto';
                    setError('Analisi fallita: ' + errorMessage);
                    setSimulationProgress('');
                    break;
                }
                attempts++;
            }

            if (attempts >= maxAttempts) {
                setError('Timeout della simulazione (2 minuti)');
                setSimulationProgress('');
            }
        } catch (err) {
            setError('Impossibile avviare la simulazione');
            setSimulationProgress('');
            console.error('Simulation error:', err);
        } finally {
            setIsSimulating(false);
        }
    }, [currentQuery, onRunSwitch, hasChanges, selectedAgent, editedSystemPrompt, editedUserPrompt]);

    // Handle Save as Default
    const handleSaveDefault = useCallback(async () => {
        if (!canSave) return;

        const agentName = getAgentNameForStep(selectedAgent);
        setError(null);
        try {
            // Save system prompt
            await apiClient.put(`/prompts/overrides/${agentName}/system`, { text: editedSystemPrompt });

            // Save user template
            await apiClient.put(`/prompts/overrides/${agentName}/user`, { text: editedUserPrompt });

            setSuccessMessage('Prompt dell\'agent aggiornati globalmente!');
            setOriginalSystemPrompt(editedSystemPrompt);
            setOriginalUserPrompt(editedUserPrompt);
            setSimulatedRunId(null);

            setTimeout(() => setSuccessMessage(null), 3000);
        } catch (err: unknown) {
            if (err && typeof err === 'object' && 'response' in err) {
                const axiosErr = err as { response?: { data?: { detail?: string } } };
                setError(axiosErr.response?.data?.detail || 'Impossibile salvare i prompt');
            } else if (err instanceof Error) {
                setError(err.message);
            } else {
                setError('Impossibile salvare i prompt');
            }
        }
    }, [canSave, selectedAgent, editedSystemPrompt, editedUserPrompt]);

    // Handle Revert
    const handleRevert = useCallback(() => {
        setEditedSystemPrompt(originalSystemPrompt);
        setEditedUserPrompt(originalUserPrompt);
        setSimulatedRunId(null);
        setError(null);
        setSuccessMessage(null);
    }, [originalSystemPrompt, originalUserPrompt]);

    // Handle Reset to Default
    const handleResetToDefault = useCallback(async () => {
        if (!selectedAgent) return;

        const agentName = getAgentNameForStep(selectedAgent);
        setIsResettingToDefault(true);
        setError(null);
        setSuccessMessage(null);

        try {
            await apiClient.post(`/prompts/reset/${agentName}`);

            // Reload prompts from API
            const [systemResp, userResp] = await Promise.all([
                apiClient.get(`/prompts/overrides/${agentName}/system`),
                apiClient.get(`/prompts/overrides/${agentName}/user`),
            ]);

            const systemData = systemResp.data;
            const userData = userResp.data;

            setOriginalSystemPrompt(systemData.text || '');
            setOriginalUserPrompt(userData.text || '');
            setEditedSystemPrompt(systemData.text || '');
            setEditedUserPrompt(userData.text || '');

            setSuccessMessage('Prompt ripristinati ai valori di default!');
            setTimeout(() => setSuccessMessage(null), 3000);
        } catch (err: unknown) {
            if (err && typeof err === 'object' && 'response' in err) {
                const axiosErr = err as { response?: { data?: { detail?: string } } };
                setError(axiosErr.response?.data?.detail || 'Errore durante il reset');
            } else if (err instanceof Error) {
                setError(err.message);
            } else {
                setError('Errore durante il reset');
            }
        } finally {
            setIsResettingToDefault(false);
        }
    }, [selectedAgent]);

    // Build context variables
    const contextVariables: Record<string, string> = {
        query: currentQuery || '',
    };

    // Get available agents
    const availableAgents = agentSteps
        .filter((s) => s.prompt?.system || s.prompt?.user)
        .map((s) => ({ key: s.key, label: s.label }));

    // Get selected agent label
    const selectedAgentLabel = availableAgents.find(a => a.key === selectedAgent)?.label || selectedAgent;

    return (
        <>
            {/* Trigger Button - styled like MapLegend */}
            <div className={className}>
                <TriggerButton
                    isOpen={isOpen}
                    onClick={onToggle}
                    hasActiveRun={!!activeRunId}
                />
            </div>

            {/* Modal Overlay */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-1000 flex items-center justify-center p-8"
                    >
                        {/* Backdrop */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
                            onClick={onToggle}
                        />

                        {/* Modal Content */}
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: 20 }}
                            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                            className="relative w-full max-w-5xl h-[85vh] bg-[#0f1218] rounded-3xl border border-white/10 shadow-2xl shadow-black/50 flex flex-col overflow-hidden"
                        >
                            {/* Ambient glow */}
                            <div className="absolute -top-40 -right-40 w-80 h-80 bg-violet-500/10 rounded-full blur-[100px] pointer-events-none" />
                            <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-cyan-500/10 rounded-full blur-[100px] pointer-events-none" />

                            {/* Header */}
                            <div className="relative flex items-center justify-between px-8 py-6 border-b border-white/10">
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 rounded-2xl bg-linear-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
                                        <Sparkles className="w-6 h-6 text-white" />
                                    </div>
                                    <div>
                                        <h2 className="text-xl font-bold text-white">Agent Tuner</h2>
                                        <p className="text-sm text-gray-500">Modifica e valida il comportamento dell'AI</p>
                                    </div>
                                </div>

                                <div className="flex items-center gap-4">
                                    {/* Run Info */}
                                    {activeRunId && (
                                        <div className="flex items-center gap-3 px-4 py-2 rounded-xl bg-white/5 border border-white/10">
                                            <Hash className="w-4 h-4 text-gray-500" />
                                            <span className="font-mono text-sm text-gray-400">{activeRunId.slice(0, 8)}...</span>
                                            {simulatedRunId && (
                                                <div className="flex items-center gap-1.5 text-emerald-400">
                                                    <Check className="w-4 h-4" />
                                                    <span className="text-xs font-medium">Simulato</span>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Close Button */}
                                    <button
                                        onClick={onToggle}
                                        className="p-3 rounded-xl hover:bg-white/5 text-gray-500 hover:text-white transition-colors"
                                    >
                                        <X className="w-5 h-5" />
                                    </button>
                                </div>
                            </div>

                            {/* Content */}
                            <div className="relative flex-1 flex flex-col min-h-0 p-8">
                                {isLoading ? (
                                    <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                                        <Loader2 className="w-10 h-10 animate-spin mb-4 text-violet-500" />
                                        <span className="text-base">Caricamento dati agent...</span>
                                    </div>
                                ) : !activeRunId ? (
                                    <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                                        <AlertCircle className="w-12 h-12 mb-4" />
                                        <span className="text-lg font-medium">Nessun run attivo</span>
                                        <p className="text-sm text-gray-600 mt-2">Carica un run dalla mappa per modificare gli agent</p>
                                    </div>
                                ) : (
                                    <div className="flex-1 flex flex-col min-h-0 gap-6">
                                        {/* Agent Selector */}
                                        {availableAgents.length > 0 && (
                                            <div className="flex items-center gap-3">
                                                <span className="text-sm text-gray-500">Agent:</span>
                                                <div className="flex flex-wrap gap-2">
                                                    {availableAgents.map((agent) => (
                                                        <button
                                                            key={agent.key}
                                                            onClick={() => handleAgentChange(agent.key)}
                                                            className={`
                                                                px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200
                                                                ${selectedAgent === agent.key
                                                                    ? 'bg-violet-500/20 text-violet-400 border border-violet-500/50 shadow-lg shadow-violet-500/10'
                                                                    : 'bg-white/5 text-gray-400 border border-white/10 hover:border-white/20 hover:bg-white/10'
                                                                }
                                                            `}
                                                        >
                                                            {agent.label}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Context Variables */}
                                        <VariableContext variables={contextVariables} />

                                        {/* Prompt Tabs - System / User */}
                                        <div className="flex items-center gap-2 mb-2">
                                            <button
                                                onClick={() => setActiveTab('system')}
                                                className={`
                                                    flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
                                                    ${activeTab === 'system'
                                                        ? 'bg-violet-500/20 text-violet-400 border border-violet-500/40'
                                                        : 'bg-white/5 text-gray-400 border border-white/10 hover:border-white/20'
                                                    }
                                                `}
                                            >
                                                <Code2 className="w-4 h-4" />
                                                System Prompt
                                            </button>
                                            <button
                                                onClick={() => setActiveTab('user')}
                                                className={`
                                                    flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
                                                    ${activeTab === 'user'
                                                        ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
                                                        : 'bg-white/5 text-gray-400 border border-white/10 hover:border-white/20'
                                                    }
                                                `}
                                            >
                                                <MessageSquare className="w-4 h-4" />
                                                User Template
                                            </button>
                                        </div>

                                        {/* Prompt Editor - Shows active tab */}
                                        {activeTab === 'system' ? (
                                            <PromptEditor
                                                value={editedSystemPrompt}
                                                onChange={setEditedSystemPrompt}
                                                label="System Prompt"
                                                agentLabel={`${selectedAgentLabel} - Istruzioni di ruolo e comportamento`}
                                                placeholder="Nessun system prompt disponibile per questo agent"
                                            />
                                        ) : (
                                            <PromptEditor
                                                value={editedUserPrompt}
                                                onChange={setEditedUserPrompt}
                                                label="User Template"
                                                agentLabel={`${selectedAgentLabel} - Template con variabili (es. {query})`}
                                                placeholder="Nessun user template disponibile per questo agent"
                                            />
                                        )}

                                        {/* Status Messages */}
                                        <AnimatePresence>
                                            {error && (
                                                <motion.div
                                                    initial={{ opacity: 0, y: -10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    exit={{ opacity: 0, y: -10 }}
                                                    className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400"
                                                >
                                                    <AlertCircle className="w-5 h-5 shrink-0" />
                                                    <span className="text-sm">{error}</span>
                                                </motion.div>
                                            )}
                                            {successMessage && (
                                                <motion.div
                                                    initial={{ opacity: 0, y: -10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    exit={{ opacity: 0, y: -10 }}
                                                    className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400"
                                                >
                                                    <Check className="w-5 h-5 shrink-0" />
                                                    <span className="text-sm">{successMessage}</span>
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </div>
                                )}
                            </div>

                            {/* Footer - Action Buttons */}
                            {activeRunId && !isLoading && (
                                <div className="relative px-8 py-6 border-t border-white/10 bg-white/2">
                                    <div className="flex items-center justify-between">
                                        <p className="text-xs text-gray-600">
                                            Modalità esperto • Le modifiche salvate influenzeranno tutte le future analisi
                                        </p>

                                        <div className="flex items-center gap-3">
                                            {/* Reset to Default */}
                                            <button
                                                onClick={handleResetToDefault}
                                                disabled={isSimulating || isResettingToDefault}
                                                className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 bg-white/5 text-gray-400 border border-white/10 hover:bg-amber-500/10 hover:text-amber-400 hover:border-amber-500/30"
                                                title="Ripristina prompt di default per questo agent"
                                            >
                                                {isResettingToDefault ? (
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                ) : (
                                                    <RotateCcw className="w-4 h-4" />
                                                )}
                                                Default
                                            </button>

                                            {/* Revert */}
                                            <button
                                                onClick={handleRevert}
                                                disabled={isSimulating || !hasChanges}
                                                className={`
                                                    flex items-center gap-2 px-5 py-2.5 rounded-xl
                                                    font-medium text-sm transition-all duration-200
                                                    ${hasChanges
                                                        ? 'bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10'
                                                        : 'bg-white/2 text-gray-600 cursor-not-allowed'
                                                    }
                                                `}
                                            >
                                                <RotateCcw className="w-4 h-4" />
                                                Annulla
                                            </button>

                                            {/* Save as Default */}
                                            <button
                                                onClick={handleSaveDefault}
                                                disabled={!canSave || isSimulating}
                                                className={`
                                                    flex items-center gap-2 px-5 py-2.5 rounded-xl
                                                    font-medium text-sm transition-all duration-200
                                                    ${canSave
                                                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30'
                                                        : 'bg-white/2 text-gray-600 cursor-not-allowed'
                                                    }
                                                `}
                                                title={canSave ? 'Salva come default globale' : 'Esegui prima una simulazione'}
                                            >
                                                <Save className="w-4 h-4" />
                                                Salva Default
                                            </button>

                                            {/* Simulate Button */}
                                            <button
                                                onClick={handleReRun}
                                                disabled={isSimulating}
                                                className={`
                                                    flex items-center gap-2 px-6 py-2.5 rounded-xl
                                                    font-semibold text-sm transition-all duration-200
                                                    ${isSimulating
                                                        ? 'bg-violet-500/20 text-violet-400 cursor-wait'
                                                        : 'bg-linear-to-r from-violet-500 to-purple-500 text-white hover:shadow-lg hover:shadow-violet-500/25 hover:scale-[1.02]'
                                                    }
                                                `}
                                            >
                                                {isSimulating ? (
                                                    <>
                                                        <Loader2 className="w-4 h-4 animate-spin" />
                                                        {simulationProgress || 'Simulazione...'}
                                                    </>
                                                ) : (
                                                    <>
                                                        <Play className="w-4 h-4" />
                                                        {hasChanges ? 'Salva e Simula' : 'Ri-esegui Analisi'}
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};

export default AgentRefinementHUD;
