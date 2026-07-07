import { motion } from 'framer-motion';
import { CheckCircle2, XCircle, Loader2, Building2, ArrowRight } from 'lucide-react';
import type { AnalysisHistoryItem } from '../../api/types';
import type { Language } from '../../contexts/SettingsContext';
import type { TranslationKeys } from '../../utils/translations';
import { QueryTooltip } from '../common/QueryTooltip';

interface HistoryItemProps {
    item: AnalysisHistoryItem;
    index: number;
    language: Language;
    translations: Record<Language, TranslationKeys>;
    onClick: (item: AnalysisHistoryItem) => void;
}

export const HistoryItem = ({ item, index, language, translations, onClick }: HistoryItemProps) => {
    const t = translations[language];

    return (
        <motion.button
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 * index }}
            onClick={() => onClick(item)}
            className="
                w-full p-4 rounded-xl bg-(--bg-surface)/60 border border-(--border-dim)
                hover:bg-(--bg-surface) hover:border-(--border-light)
                transition-all duration-300 text-left group
                overflow-hidden backdrop-blur-sm
            "
        >
            <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider border ${
                            item.status === 'completed'
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                : item.status === 'failed'
                                    ? 'bg-red-500/10 text-red-500 border-red-500/20'
                                    : 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                        }`}>
                            {item.status === 'completed' ? (
                                <>
                                    <CheckCircle2 className="w-3 h-3" />
                                    {t.search.status.completed}
                                </>
                            ) : item.status === 'failed' ? (
                                <>
                                    <XCircle className="w-3 h-3" />
                                    {t.search.status.failed}
                                </>
                            ) : (
                                <>
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                    {t.search.status.processing}
                                </>
                            )}
                        </span>
                        <span className="text-xs text-(--text-tertiary) font-medium">
                            {new Date(item.created_at).toLocaleDateString(language === 'it' ? 'it-IT' : 'en-US', {
                                day: 'numeric',
                                month: 'short',
                                hour: '2-digit',
                                minute: '2-digit',
                            })}
                        </span>
                    </div>
                    <QueryTooltip text={item.query}>
                        <p
                            className={`text-sm font-medium leading-relaxed group-hover:text-(--accent-cyan) transition-colors break-words [overflow-wrap:anywhere] ${
                                item.status === 'failed' ? 'text-(--text-tertiary)' : 'text-(--text-primary)'
                            }`}
                            style={{
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                            }}
                        >
                            {item.query}
                        </p>
                    </QueryTooltip>
                    
                    <div className="flex items-center gap-3 mt-2">
                        {item.status === 'completed' && item.buildings_count !== undefined && (
                            <div className="flex items-center gap-1.5 text-xs text-(--text-tertiary)">
                                <Building2 className="w-3.5 h-3.5" />
                                <span>{item.buildings_count} {t.search.propertyFound}</span>
                            </div>
                        )}
                        {item.status === 'failed' && (
                            <div className="text-xs text-red-400/80 font-medium">
                                {t.search.error}
                            </div>
                        )}
                    </div>
                </div>
                <div className="mt-1">
                    <ArrowRight className="w-4 h-4 text-(--text-tertiary) group-hover:text-(--accent-cyan) group-hover:translate-x-1 transition-all duration-300" />
                </div>
            </div>
        </motion.button>
    );
};
