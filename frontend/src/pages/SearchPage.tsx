/**
 * SearchPage - AI Command Center Home
 *
 * Main search interface with:
 * - Refined glassmorphism Command Bar
 * - Design-token based styling
 * - Decoupled HistoryItem component
 * - Suggestion system
 */

import React, { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
    Search,
    ArrowRight,
    Clock,
    Loader2,
    Send,
    Sparkles,
    UserRound,
    RotateCcw,
} from 'lucide-react';
import { useAnalysis } from '../hooks/useAnalysis';
import { useSettings } from '../contexts/SettingsContext';
import { translations } from '../utils/translations';
import { analysisApi } from '../api/endpoints/analysis';
import type { AnalysisHistoryItem } from '../api/types';
import { HistoryItem } from '../components/search/HistoryItem';

const SUGGESTED_QUERIES = {
    it: [
        'Trova un grande meta-edificio residenziale vicino a Porta Nuova adatto alla conversione in co-housing o social housing, con almeno 600 mq, classe energetica bassa E, F o G, ottima accessibilita al trasporto pubblico e preferibilmente vicino ad aree verdi o impianti sportivi',
        'Trova edifici direzionali o commerciali vicino al Politecnico di Torino convertibili in residenze universitarie o servizi pubblici, con almeno 200 mq, classe energetica A, B o C, forte accessibilita al trasporto pubblico e buona prossimita a istruzione e aree verdi',
        'Uffici vicino a Porta Nuova con classe energetica alta',
        'Edifici di almeno 1000 mq vicino al Politecnico',
        'Spazi commerciali in centro comodi ai trasporti',
    ],
    en: [
        'Find a large residential meta-building near Porta Nuova suitable for co-housing or social housing conversion, with at least 600 sqm, low energy class E, F or G, excellent public transport accessibility, and preferably close to green areas or sports facilities',
        'Find office or commercial buildings near the Politecnico di Torino that could be converted into student housing or public services, with at least 200 sqm, energy class A, B or C, strong public transport accessibility, and good proximity to education and green areas',
        'Offices near Porta Nuova with a high energy class',
        'Buildings of at least 1000 sqm near the Polytechnic University',
        'Retail spaces in the city center with convenient public transport',
    ],
} as const;

import murenaLogo217 from '../assets/brand/MURENA_217x34px.svg';

type ClarificationMessage = {
    role: 'user' | 'assistant' | 'system';
    content: string;
};

export const SearchPage: React.FC = () => {
    const navigate = useNavigate();
    const { dataSource, language, llmLimit, markersLimit } = useSettings();
    const [query, setQuery] = useState('');
    const [isFocused, setIsFocused] = useState(false);
    const [recentHistory, setRecentHistory] = useState<AnalysisHistoryItem[]>([]);
    const [isLoadingHistory, setIsLoadingHistory] = useState(true);
    const [availableDemos, setAvailableDemos] = useState<string[]>([]);
    const [clarificationSessionId, setClarificationSessionId] = useState<string | null>(null);
    const [clarificationError, setClarificationError] = useState<string | null>(null);
    const [clarificationOriginalQuery, setClarificationOriginalQuery] = useState('');
    const [clarificationMessages, setClarificationMessages] = useState<ClarificationMessage[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const { loadDemo, status, runId, isLoading } = useAnalysis();
    const busy = isLoading || isSubmitting;

    const t = translations[language];
    const suggestions = SUGGESTED_QUERIES[language];

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [query]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, [clarificationMessages, isSubmitting]);

    useEffect(() => {
        if (clarificationSessionId) textareaRef.current?.focus();
    }, [clarificationSessionId]);

    // Fetch recent history and demos on mount
    useEffect(() => {
        const fetchData = async () => {
            try {
                const [history, demos] = await Promise.all([
                    analysisApi.getHistory(10),
                    analysisApi.getDemos().catch(() => []),
                ]);
                setRecentHistory(history.slice(0, 3));
                setAvailableDemos(demos);
            } catch (err) {
                console.error('Failed to fetch data:', err);
            } finally {
                setIsLoadingHistory(false);
            }
        };
        fetchData();
    }, []);

    // Navigate to processing when analysis starts
    useEffect(() => {
        if (status === 'processing' && runId) {
            navigate(`/processing/${runId}`);
        }
    }, [status, runId, navigate]);

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!query.trim() || busy) return;

        const submittedText = query.trim();
        const isClarificationTurn = Boolean(clarificationSessionId);
        if (isClarificationTurn) {
            setClarificationMessages((messages) => [
                ...messages,
                { role: 'user', content: submittedText },
            ]);
            setQuery('');
        }

        try {
            if (!isClarificationTurn && dataSource === 'sandbox' && availableDemos.length > 0) {
                const id = await loadDemo(availableDemos[0]);
                navigate(`/processing/${id}`);
            } else {
                setIsSubmitting(true);
                setClarificationError(null);
                const original = isClarificationTurn ? clarificationOriginalQuery : submittedText;
                const result = await analysisApi.submitAnalysis({
                    query: original,
                    llm_limit: llmLimit,
                    map_limit: markersLimit,
                    output_language: language,
                    clarification_session_id: clarificationSessionId ?? undefined,
                    clarification_response: clarificationSessionId ? query.trim() : undefined,
                });
                if ('session_id' in result) {
                    if (result.status === 'ASK') {
                        if (!isClarificationTurn) {
                            setClarificationOriginalQuery(submittedText);
                            setClarificationMessages([
                                { role: 'user', content: submittedText },
                                { role: 'assistant', content: result.question || 'Please clarify your request.' },
                            ]);
                        } else {
                            setClarificationMessages((messages) => [
                                ...messages,
                                { role: 'assistant', content: result.question || 'Please clarify your request.' },
                            ]);
                        }
                        setClarificationSessionId(result.session_id);
                        setQuery('');
                    } else {
                        const message = result.message || 'Clarification cannot continue safely.';
                        if (isClarificationTurn) {
                            setClarificationMessages((messages) => [
                                ...messages,
                                { role: 'system', content: message },
                            ]);
                        } else {
                            setClarificationError(message);
                        }
                        setClarificationSessionId(null);
                    }
                } else {
                    setClarificationSessionId(null);
                    navigate(`/processing/${result.run_id}`);
                }
            }
        } catch (err) {
            console.error('Failed to start analysis:', err);
            setClarificationError(err instanceof Error ? err.message : 'Failed to start analysis.');
            if (isClarificationTurn) {
                setClarificationMessages((messages) => messages.slice(0, -1));
                setQuery(submittedText);
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    const startNewSearch = () => {
        setClarificationMessages([]);
        setClarificationSessionId(null);
        setClarificationError(null);
        setQuery(clarificationOriginalQuery);
    };

    const handleSuggestionClick = (suggestion: string) => {
        setQuery(suggestion);
        textareaRef.current?.focus();
    };

    const handleHistoryClick = (item: AnalysisHistoryItem) => {
        navigate(`/map?run_id=${item.run_id}`);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <div className="min-h-full relative flex flex-col items-center justify-center p-8 overflow-x-hidden bg-(--bg-main)">
            {/* Background Image with refined layer */}
            <div
                className="absolute inset-0 z-0 opacity-40 scale-105 pointer-events-none"
                style={{
                    backgroundImage: 'url(/backgrounds/buildings.jpg)',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center bottom',
                    backgroundRepeat: 'no-repeat',
                }}
            />
            {/* Gradient overlays with design tokens */}
            <div className="absolute inset-0 z-0 bg-linear-to-b from-(--bg-main) via-(--bg-main)/90 to-(--bg-main)/95 pointer-events-none" />
            <div className="absolute inset-0 z-0 bg-linear-to-t from-(--bg-main) via-transparent to-transparent opacity-80 pointer-events-none" />

            {/* Main Content */}
            <div className="w-full max-w-3xl mx-auto relative z-10">

                {/* Logo Murena */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-center mb-10"
                >
                    <img src={murenaLogo217} alt="Murena" className="w-[300px] h-auto" />
                </motion.div>

                {/* Initial search composer */}
                {clarificationMessages.length === 0 && (
                <motion.form
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    onSubmit={handleSubmit}
                    className="relative mb-10"
                >
                    <div className={`
                        relative bg-(--glass-bg) backdrop-blur-2xl rounded-2xl border transition-all duration-500 overflow-hidden
                        ${isFocused
                            ? 'border-(--accent-cyan)/50 ring-4 ring-(--accent-cyan)/10 shadow-2xl scale-[1.01]'
                            : 'border-(--border-light) hover:border-(--border-light)/30'
                        }
                    `}>
                        <div className="absolute left-6 top-1/2 -translate-y-1/2 text-(--text-tertiary)">
                            <Search className="w-5 h-5" />
                        </div>

                        <div className="flex items-stretch">
                            <textarea
                                ref={textareaRef}
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onFocus={() => setIsFocused(true)}
                                onBlur={() => setIsFocused(false)}
                                onKeyDown={handleKeyDown}
                                placeholder={t.search.placeholder}
                                rows={1}
                                className="
                                    flex-1 bg-transparent text-(--text-primary) placeholder-(--text-tertiary)
                                    pl-16 pr-6 py-6 text-lg font-medium resize-none outline-none
                                    min-h-[72px] max-h-[200px]
                                "
                                disabled={busy}
                            />

                            <div className="shrink-0 pr-4 pl-2 flex items-center">
                                <motion.button
                                    type="submit"
                                    disabled={!query.trim() || busy}
                                    whileHover={{ scale: 1.05 }}
                                    whileTap={{ scale: 0.95 }}
                                    className={`
                                        flex items-center gap-3 px-6 py-3 rounded-xl font-bold text-sm tracking-wide uppercase
                                        transition-all duration-300
                                        ${query.trim() && !busy
                                            ? 'bg-linear-to-r from-emerald-600 to-cyan-600 text-white shadow-lg shadow-emerald-500/30'
                                            : 'bg-white/5 text-(--text-tertiary) cursor-not-allowed'
                                        }
                                    `}
                                >
                                    {busy ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <>
                                            <span>{t.search.submit}</span>
                                            <ArrowRight className="w-5 h-5" />
                                        </>
                                    )}
                                </motion.button>
                            </div>
                        </div>
                    </div>
                </motion.form>
                )}

                {clarificationMessages.length > 0 && (
                    <motion.section
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="-mt-2 mb-10 overflow-hidden rounded-3xl border border-(--border-light) bg-(--glass-bg)/90 shadow-2xl backdrop-blur-2xl"
                        aria-label={language === 'it' ? 'Conversazione di ricerca' : 'Search conversation'}
                    >
                        <header className="border-b border-(--border-light) px-6 py-5 sm:px-8">
                            <div className="flex items-center gap-3">
                                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300">
                                    <Sparkles className="h-5 w-5" />
                                </span>
                                <div>
                                    <h2 className="font-semibold text-(--text-primary)">
                                        {language === 'it' ? 'Affiniamo la ricerca' : 'Let’s refine your search'}
                                    </h2>
                                    <p className="text-xs text-(--text-tertiary)">
                                        {language === 'it'
                                            ? 'Una breve conversazione prima di avviare l’analisi.'
                                            : 'A short conversation before the analysis starts.'}
                                    </p>
                                </div>
                            </div>
                        </header>

                        <div className="max-h-[48vh] space-y-5 overflow-y-auto px-5 py-6 sm:px-8" aria-live="polite">
                            {clarificationMessages.map((message, index) => (
                                <div
                                    key={`${message.role}-${index}`}
                                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                >
                                    <div className={`flex max-w-[88%] items-end gap-2.5 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                        {message.role !== 'system' && (
                                            <span className={`mb-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                                                message.role === 'user'
                                                    ? 'bg-cyan-500/15 text-cyan-200'
                                                    : 'bg-emerald-500/15 text-emerald-300'
                                            }`}>
                                                {message.role === 'user'
                                                    ? <UserRound className="h-4 w-4" />
                                                    : <Sparkles className="h-4 w-4" />}
                                            </span>
                                        )}
                                        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                                            message.role === 'user'
                                                ? 'rounded-br-md bg-cyan-600/25 text-(--text-primary)'
                                                : message.role === 'system'
                                                    ? 'w-full border border-amber-400/30 bg-amber-500/10 text-amber-100'
                                                    : 'rounded-bl-md border border-(--border-light) bg-white/5 text-(--text-primary)'
                                        }`}>
                                            {message.role === 'assistant' && (
                                                <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-emerald-300">
                                                    {language === 'it' ? 'MURENA · Chiarimento' : 'MURENA · Clarification'}
                                                </p>
                                            )}
                                            <p className="whitespace-pre-wrap">{message.content}</p>
                                            {message.role === 'system' && (
                                                <button type="button" className="mt-3 inline-flex items-center gap-2 font-medium underline underline-offset-4" onClick={startNewSearch}>
                                                    <RotateCcw className="h-3.5 w-3.5" />
                                                    {language === 'it' ? 'Avvia una nuova ricerca' : 'Start a new search'}
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {isSubmitting && (
                                <div className="flex items-center gap-3 pl-10 text-xs text-(--text-tertiary)" role="status">
                                    <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                                    {language === 'it' ? 'Sto valutando la risposta…' : 'Considering your answer…'}
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {clarificationSessionId ? (
                            <form onSubmit={handleSubmit} className="border-t border-(--border-light) bg-black/10 p-4 sm:px-6">
                                {clarificationError && (
                                    <p className="mb-3 text-sm text-amber-200" role="alert">{clarificationError}</p>
                                )}
                                <div className="flex items-end gap-3 rounded-2xl border border-(--border-light) bg-black/20 p-2 focus-within:border-(--accent-cyan)/50">
                                    <textarea
                                        ref={textareaRef}
                                        value={query}
                                        onChange={(event) => setQuery(event.target.value)}
                                        onKeyDown={handleKeyDown}
                                        placeholder={language === 'it' ? 'Scrivi la tua risposta…' : 'Type your answer…'}
                                        rows={1}
                                        disabled={busy}
                                        aria-label={language === 'it' ? 'La tua risposta' : 'Your answer'}
                                        className="max-h-36 min-h-11 flex-1 resize-none bg-transparent px-3 py-3 text-sm text-(--text-primary) outline-none placeholder:text-(--text-tertiary)"
                                    />
                                    <button
                                        type="submit"
                                        disabled={!query.trim() || busy}
                                        className="flex h-11 shrink-0 items-center gap-2 rounded-xl bg-linear-to-r from-emerald-600 to-cyan-600 px-4 font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
                                    >
                                        {busy
                                            ? <Loader2 className="h-4 w-4 animate-spin" />
                                            : <><span>{language === 'it' ? 'Invia' : 'Send'}</span><Send className="h-4 w-4" /></>}
                                    </button>
                                </div>
                                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 px-1 text-[11px] text-(--text-tertiary)">
                                    <span>{language === 'it'
                                        ? 'Dopo ogni risposta, MURENA passerà al prossimo requisito da chiarire.'
                                        : 'After each answer, MURENA will move to the next requirement to clarify.'}</span>
                                    <div className="flex items-center gap-4">
                                        <button
                                            type="button"
                                            className="underline underline-offset-2 hover:text-(--text-secondary)"
                                            onClick={() => setQuery(language === 'it' ? 'Non mi interessa' : 'Not relevant')}
                                        >
                                            {language === 'it' ? 'Non mi interessa' : 'Not relevant'}
                                        </button>
                                        <button type="button" className="underline underline-offset-2 hover:text-(--text-secondary)" onClick={startNewSearch}>
                                            {language === 'it' ? 'Annulla' : 'Cancel'}
                                        </button>
                                    </div>
                                </div>
                            </form>
                        ) : null}
                    </motion.section>
                )}
                {clarificationError && (
                    clarificationMessages.length === 0 && (
                    <div className="-mt-6 mb-8 rounded-xl border border-amber-400/30 bg-amber-500/10 px-5 py-4 text-sm text-amber-100" role="alert">
                        <p>{clarificationError}</p>
                        <button
                            type="button"
                            className="mt-2 underline"
                            onClick={() => {
                                setClarificationError(null);
                                setClarificationSessionId(null);
                                setClarificationMessages([]);
                                setQuery(clarificationOriginalQuery);
                            }}
                        >{language === 'it' ? 'Avvia una nuova ricerca' : 'Start a new search'}</button>
                    </div>
                    )
                )}

                {/* Suggestions */}
                {clarificationMessages.length === 0 && <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="flex flex-wrap items-center justify-center gap-4 mb-20"
                >
                    <span className="text-sm text-(--text-tertiary) font-medium uppercase tracking-widest">{t.search.suggested}</span>
                    {suggestions.map((suggestion, i) => (
                        <button
                            key={i}
                            onClick={() => handleSuggestionClick(suggestion)}
                            className="text-sm font-semibold text-emerald-400/80 hover:text-emerald-300 hover:underline decoration-emerald-500/30 underline-offset-4 transition-all"
                        >
                            {suggestion}
                        </button>
                    ))}
                </motion.div>}

                {/* Recent History */}
                {clarificationMessages.length === 0 && <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.5 }}
                    className="space-y-6"
                >
                    <div className="flex items-center justify-between px-2">
                        <div className="flex items-center gap-3">
                            <Clock className="w-4 h-4 text-emerald-500/60" />
                            <h3 className="text-xs font-bold uppercase tracking-widest text-(--text-tertiary)">{t.search.recentHistory}</h3>
                        </div>
                        <span className="text-[10px] font-bold text-gray-700 uppercase tracking-tighter">
                            {recentHistory.length > 0 && `${recentHistory.length} ${t.search.found}`}
                        </span>
                    </div>

                    {isLoadingHistory ? (
                        <div className="flex items-center justify-center py-16">
                            <Loader2 className="w-6 h-6 text-emerald-500 animate-spin" />
                        </div>
                    ) : recentHistory.length === 0 ? (
                        <div className="text-center py-16 text-(--text-tertiary) text-sm bg-white/5 rounded-2xl border border-dashed border-(--border-light)">
                            {t.search.noHistory}
                        </div>
                    ) : (
                        <div className="grid gap-4">
                            {recentHistory.map((item, i) => (
                                <HistoryItem
                                    key={item.run_id}
                                    item={item}
                                    index={i}
                                    language={language}
                                    translations={translations}
                                    onClick={handleHistoryClick}
                                />
                            ))}
                        </div>
                    )}
                </motion.div>}
            </div>
        </div>
    );
};

export default SearchPage;
