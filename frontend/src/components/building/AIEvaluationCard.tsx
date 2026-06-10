import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, CheckCircle2, AlertTriangle, ChevronDown, ChevronUp, Sliders, Zap, MapPin, Activity, Shield, Building2 } from 'lucide-react';

interface AIEvaluationCardProps {
    score?: number;
    evaluationText?: string;
    pros?: string[];
    cons?: string[];
    compact?: boolean; // For smaller display in sidebar
    energyScores?: any;
    proximityScores?: any;
    distanceKm?: number;
    locationScore?: number;
    regulatoryScore?: number;
    energyScore?: number;
    buildingScore?: number;
    proximityScore?: number;
    weightLocation?: number;
    weightRegulatory?: number;
    weightEnergy?: number;
    weightBuilding?: number;
    weightProximity?: number;
}

export const AIEvaluationCard: React.FC<AIEvaluationCardProps> = ({
    score,
    evaluationText,
    pros = [],
    cons = [],
    compact = false,
    energyScores,
    proximityScores,
    distanceKm,
    locationScore,
    regulatoryScore,
    energyScore,
    buildingScore,
    proximityScore,
    weightLocation,
    weightRegulatory,
    weightEnergy,
    weightBuilding,
    weightProximity,
}) => {
    const [showBreakdown, setShowBreakdown] = useState(false);

    const hasWeights = weightLocation !== undefined || weightRegulatory !== undefined || weightEnergy !== undefined || weightBuilding !== undefined || weightProximity !== undefined;
    const wLoc = hasWeights ? (weightLocation ?? 0.0) : 0.3;
    const wReg = hasWeights ? (weightRegulatory ?? 0.0) : 0.0;
    const wEng = hasWeights ? (weightEnergy ?? 0.0) : 0.2;
    const wBld = hasWeights ? (weightBuilding ?? 0.0) : 0.0;
    const wProx = hasWeights ? (weightProximity ?? 0.0) : 0.5;

    const getScoreColor = (s?: number) => {
        if (!s) return { bg: 'from-gray-600 to-gray-700', text: 'text-gray-400', glow: 'shadow-gray-500/20' };
        if (s >= 80) return { bg: 'from-emerald-500 to-green-600', text: 'text-emerald-400', glow: 'shadow-emerald-500/30' };
        if (s >= 60) return { bg: 'from-cyan-500 to-blue-600', text: 'text-cyan-400', glow: 'shadow-cyan-500/30' };
        if (s >= 40) return { bg: 'from-amber-500 to-orange-600', text: 'text-amber-400', glow: 'shadow-amber-500/30' };
        return { bg: 'from-red-500 to-rose-600', text: 'text-red-400', glow: 'shadow-red-500/30' };
    };

    const scoreColors = getScoreColor(score);
    const hasEvaluation = score != null || evaluationText || pros.length > 0 || cons.length > 0;

    // Helper score calculations for breakdown
    const getPoiScore = () => {
        if (proximityScore !== undefined && proximityScore !== null) return Math.round(proximityScore);
        if (!proximityScores) return 70; // fallback default
        const values = Object.values(proximityScores).filter(v => v !== undefined && v !== null && typeof v === 'number') as number[];
        if (values.length === 0) return 70;
        const avg = values.reduce((sum, v) => sum + v, 0) / values.length;
        return Math.round(avg);
    };

    const getApeScore = () => {
        if (energyScore !== undefined && energyScore !== null) return Math.round(energyScore);
        if (!energyScores) return 60; // fallback default
        if (energyScores.total !== undefined && energyScores.total !== null) {
            return Math.round((energyScores.total / 20) * 100);
        }
        const keys = ['class_score', 'system_score', 'envelope_score', 'renewables_score'];
        const values = keys.map(k => energyScores[k]).filter(v => v !== undefined && v !== null && typeof v === 'number') as number[];
        if (values.length === 0) return 60;
        const avg = values.reduce((sum, v) => sum + v, 0) / values.length;
        return Math.round((avg / 5) * 100);
    };

    const getDistanceScore = () => {
        if (locationScore !== undefined && locationScore !== null) return Math.round(locationScore);
        if (distanceKm === undefined || distanceKm === null) return 80; // fallback default
        const maxDist = 6.0; // standard fallback normalized dist
        const distScoreNorm = Math.max(0, 1 - (distanceKm / maxDist));
        return Math.round(distScoreNorm * 100);
    };

    const getRegulatoryScore = () => {
        if (regulatoryScore !== undefined && regulatoryScore !== null) return Math.round(regulatoryScore);
        return 0; // default/fallback
    };

    const getBuildingScore = () => {
        if (buildingScore !== undefined && buildingScore !== null) return Math.round(buildingScore);
        return 0; // default/fallback
    };

    const poi = getPoiScore();
    const energy = getApeScore();
    const location = getDistanceScore();
    const regulatory = getRegulatoryScore();
    const building = getBuildingScore();

    if (!hasEvaluation) {
        return null;
    }

    if (compact) {
        return (
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-linear-to-br from-amber-500/10 to-yellow-500/5 border border-amber-400/20 rounded-lg p-3"
            >
                <div className="flex items-center gap-3">
                    {/* Score Circle */}
                    {score != null && (
                        <div className={`w-12 h-12 rounded-full bg-linear-to-br ${scoreColors.bg} flex items-center justify-center shadow-lg ${scoreColors.glow} shrink-0`}>
                            <span className="text-white font-bold text-base">{score}</span>
                        </div>
                    )}

                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Sparkles className="w-3 h-3 text-amber-400" />
                            <span className="text-[10px] uppercase font-semibold text-amber-400 tracking-wide">
                                Valutazione AI
                            </span>
                        </div>
                        {evaluationText && (
                            <p className="text-xs text-gray-300 line-clamp-2 leading-relaxed">
                                {evaluationText}
                            </p>
                        )}
                    </div>
                </div>

                {/* Compact Pros/Cons */}
                {(pros.length > 0 || cons.length > 0) && (
                    <div className="flex items-center gap-3 mt-2 pt-2 border-t border-white/5 text-[10px]">
                        {pros.length > 0 && (
                            <span className="text-emerald-400 flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3" />
                                {pros.length} punti di forza
                            </span>
                        )}
                        {cons.length > 0 && (
                            <span className="text-amber-400 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" />
                                {cons.length} criticità
                            </span>
                        )}
                    </div>
                )}
            </motion.div>
        );
    }

    // Full display
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-linear-to-br from-amber-500/10 via-yellow-500/5 to-transparent border border-amber-400/20 rounded-xl overflow-hidden"
        >
            {/* Header - Styled like rank card */}
            <div className="px-4 py-3 bg-linear-to-r from-amber-500/10 to-transparent border-b border-amber-400/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-linear-to-br from-amber-400 to-yellow-500 flex items-center justify-center">
                        <Sparkles className="w-3.5 h-3.5 text-white" />
                    </div>
                    <span className="text-sm font-semibold text-amber-400">
                        Valutazione AI
                    </span>
                </div>

                {/* Score Badge - Styled exactly like carousel rank badge */}
                {score != null && (
                    <div className={`px-3 py-1.5 rounded-lg font-bold text-lg
                        ${score >= 80
                            ? 'bg-linear-to-br from-amber-400 to-yellow-500 text-black shadow-lg shadow-amber-500/30'
                            : score >= 60
                                ? 'bg-linear-to-br from-amber-500/80 to-orange-500/80 text-white shadow-lg shadow-amber-500/20'
                                : score >= 40
                                    ? 'bg-linear-to-br from-slate-500 to-slate-600 text-white'
                                    : 'bg-slate-700 text-gray-300'
                        }
                    `}>
                        {score}
                    </div>
                )}
            </div>

            {/* Content */}
            <div className="p-4 space-y-4">
                {/* Evaluation Text */}
                {evaluationText && (
                    <p className="text-sm text-gray-300 leading-relaxed">
                        {evaluationText}
                    </p>
                )}

                {/* Collapsible Score Formulation Detail */}
                {score != null && (
                    <div className="border border-white/10 rounded-lg overflow-hidden bg-[#1e293b]/30">
                        <button
                            onClick={() => setShowBreakdown(!showBreakdown)}
                            className="w-full px-3 py-2 flex items-center justify-between text-xs font-semibold text-gray-300 hover:bg-white/5 transition-colors"
                        >
                            <span className="flex items-center gap-1.5">
                                <Sliders className="w-3.5 h-3.5 text-amber-400" />
                                Dettaglio Formulazione Score
                            </span>
                            {showBreakdown ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>

                        <AnimatePresence>
                            {showBreakdown && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.2 }}
                                    className="px-3 pb-3 pt-1 border-t border-white/5 text-xs space-y-2.5"
                                >
                                    {/* Agent Proximity */}
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-[11px]">
                                            <span className="text-gray-400 flex items-center gap-1">
                                                <Activity className="w-3 h-3 text-emerald-400" />
                                                Agente Prossimità (POI)
                                            </span>
                                            <span className="text-white font-medium">Peso: {Math.round(wProx * 100)}% | Score: {poi}/100</span>
                                        </div>
                                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                                            <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${poi}%` }} />
                                        </div>
                                    </div>

                                    {/* Agent Location (Distance) */}
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-[11px]">
                                            <span className="text-gray-400 flex items-center gap-1">
                                                <MapPin className="w-3 h-3 text-cyan-400" />
                                                Agente Posizione (Distanza)
                                            </span>
                                            <span className="text-white font-medium">Peso: {Math.round(wLoc * 100)}% | Score: {location}/100</span>
                                        </div>
                                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                                            <div className="bg-cyan-500 h-full rounded-full" style={{ width: `${location}%` }} />
                                        </div>
                                        {distanceKm !== undefined && (
                                            <span className="text-[10px] text-gray-500">
                                                Distanza di riferimento: {distanceKm.toFixed(2)} km
                                            </span>
                                        )}
                                    </div>

                                    {/* Agent Energy (APE) */}
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-[11px]">
                                            <span className="text-gray-400 flex items-center gap-1">
                                                <Zap className="w-3 h-3 text-amber-400" />
                                                Agente Efficienza (APE)
                                            </span>
                                            <span className="text-white font-medium">Peso: {Math.round(wEng * 100)}% | Score: {energy}/100</span>
                                        </div>
                                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                                            <div className="bg-amber-500 h-full rounded-full" style={{ width: `${energy}%` }} />
                                        </div>
                                    </div>

                                    {/* Agent Regulatory */}
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-[11px]">
                                            <span className="text-gray-400 flex items-center gap-1">
                                                <Shield className="w-3 h-3 text-purple-400" />
                                                Agente Regolarità (Normativa)
                                            </span>
                                            <span className="text-white font-medium">Peso: {Math.round(wReg * 100)}% | Score: {regulatory}/100</span>
                                        </div>
                                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                                            <div className="bg-purple-500 h-full rounded-full" style={{ width: `${regulatory}%` }} />
                                        </div>
                                    </div>

                                    {/* Agent Building Technical */}
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-[11px]">
                                            <span className="text-gray-400 flex items-center gap-1">
                                                <Building2 className="w-3 h-3 text-rose-400" />
                                                Agente Caratteristiche (Tecnico)
                                            </span>
                                            <span className="text-white font-medium">Peso: {Math.round(wBld * 100)}% | Score: {building}/100</span>
                                        </div>
                                        <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                                            <div className="bg-rose-500 h-full rounded-full" style={{ width: `${building}%` }} />
                                        </div>
                                    </div>

                                    {/* Final Score Mathematical calculation */}
                                    <div className="mt-3 pt-2 border-t border-white/5 text-[10px] text-gray-400 bg-black/20 p-2 rounded-md font-mono flex flex-col gap-0.5">
                                        <span className="text-[11px] text-amber-300 font-semibold mb-1">Formula Ponderata:</span>
                                        <div className="leading-relaxed">
                                            ({poi} × {wProx.toFixed(2)}) + ({location} × {wLoc.toFixed(2)}) + ({energy} × {wEng.toFixed(2)}) + ({regulatory} × {wReg.toFixed(2)}) + ({building} × {wBld.toFixed(2)})
                                        </div>
                                        <div className="text-white font-bold mt-1.5 text-right border-t border-white/5 pt-1">
                                            = {Math.round(poi * wProx + location * wLoc + energy * wEng + regulatory * wReg + building * wBld)} / 100
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                )}

                {/* Pros */}
                {pros.length > 0 && (
                    <div>
                        <div className="flex items-center gap-1.5 mb-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wide">
                                Punti di forza
                            </span>
                        </div>
                        <ul className="space-y-1.5">
                            {pros.map((pro, index) => (
                                <motion.li
                                    key={index}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                    className="flex items-start gap-2 text-sm text-gray-300"
                                >
                                    <span className="text-emerald-400 mt-0.5">✓</span>
                                    <span>{pro}</span>
                                </motion.li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Cons */}
                {cons.length > 0 && (
                    <div>
                        <div className="flex items-center gap-1.5 mb-2">
                            <AlertTriangle className="w-4 h-4 text-amber-400" />
                            <span className="text-xs font-semibold text-amber-400 uppercase tracking-wide">
                                Criticità
                            </span>
                        </div>
                        <ul className="space-y-1.5">
                            {cons.map((con, index) => (
                                <motion.li
                                    key={index}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.05 }}
                                    className="flex items-start gap-2 text-sm text-gray-300"
                                >
                                    <span className="text-amber-400 mt-0.5">⚠</span>
                                    <span>{con}</span>
                                </motion.li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </motion.div>
    );
};
