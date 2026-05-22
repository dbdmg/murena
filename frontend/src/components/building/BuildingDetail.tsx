import React, { useMemo, useState, useEffect } from 'react';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';
import { Zap, MapPin, Building2, FileText, Shield, ChevronDown, FileCheck, Sparkles, Info, Activity } from 'lucide-react';
import type { EnergyDetail } from './EnergyDetailModal';
import { EnergyDetailModal } from './EnergyDetailModal';
import { AIEvaluationCard } from './AIEvaluationCard';
import { StreetImage } from './StreetImage';
import client from '../../api/client';
import type { MarkerTier, AgentFeedbackResponse } from '../../api/types';
import { FeedbackPanel } from '../agent/FeedbackPanel';
import { feedbackApi } from '../../api/endpoints/feedback';

// Interface matching the data structure from MapMarker/Backend
interface BuildingData {
    id: string;
    lat?: number;
    lng?: number;
    address?: string;
    city?: string;
    surface_area?: number;
    construction_year?: string;
    energy_class?: string;
    score?: number;
    price?: number;
    description?: string;
    rooms?: number;
    bathrooms?: number;
    floor?: string;
    // Extended info
    property_type?: string;
    legal_nature?: string;
    cultural_constraint?: string;
    purpose?: string;
    omi_zone?: string;
    cadastral_sheet?: string;
    cadastral_parcel?: string;
    // Energy info
    energy_scores?: {
        total?: number;
        class_score?: number;
        plant_score?: number;
        envelope_score?: number;
        renewables_score?: number;
    };
    proximity_scores?: {
        healthcare?: number;
        mobility?: number;
        greenery?: number;
        education?: number;
        commerce?: number;
        sport?: number;
    };
    energy_files?: string[];
    // User requested fields
    is_meta_building?: boolean;
    meta_property?: string;
    third_party_tenure_type?: string;
    annual_rent?: number;
    start_date?: string;
    cadastral_units_count?: number;
    id_list?: string;
    sub_properties?: {
        id: string;
        surface_area?: number;
        property_type?: string;
    }[];
    // AI Intelligence Map fields
    tier?: MarkerTier;
    evaluation_text?: string;
    pros?: string[];
    cons?: string[];
    ranking_score?: number;
    is_evaluated?: boolean;
}

interface BuildingDetailProps {
    data: BuildingData;
    runId?: string;
    onFeedbackSuccess?: () => void;
}

// Energy file info cache type
interface EnergyFileInfo {
    energy_class?: string;
    annual_cost_estimate?: number;
    loading: boolean;
}

// Helper to get color for energy class badge
const getClassBadgeColor = (cls?: string) => {
    if (!cls) return 'bg-gray-600 text-gray-300';
    const c = cls.toUpperCase();
    if (['A1', 'A2', 'A3', 'A4', 'A'].includes(c)) return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
    if (['B'].includes(c)) return 'bg-lime-500/20 text-lime-400 border border-lime-500/30';
    if (['C'].includes(c)) return 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30';
    if (['D'].includes(c)) return 'bg-orange-500/20 text-orange-400 border border-orange-500/30';
    if (['E'].includes(c)) return 'bg-orange-600/20 text-orange-500 border border-orange-600/30';
    if (['F'].includes(c)) return 'bg-red-500/20 text-red-400 border border-red-500/30';
    return 'bg-red-600/20 text-red-500 border border-red-600/30';
};

// Collapsible APE Files List Component
const EnergyFilesList: React.FC<{ files: string[]; onFileClick: (file: string) => void }> = ({ files, onFileClick }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [fileInfos, setFileInfos] = useState<Record<string, EnergyFileInfo>>({});
    const displayedFiles = isExpanded ? files : files.slice(0, 2);
    const hasMore = files.length > 2;

    // Extract filename from path for display
    const getFileName = (path: string) => {
        const parts = path.split(/[/\\]/);
        return parts[parts.length - 1] || path;
    };

    // Track fetched files to avoid dependency loop and re-renders
    const fetchedFilesRef = React.useRef<Set<string>>(new Set());

    useEffect(() => {
        let isMounted = true;

        files.forEach(file => {
            const fileName = getFileName(file);

            // Only fetch if not already fetched/fetching in this component instance
            if (!fetchedFilesRef.current.has(fileName)) {
                fetchedFilesRef.current.add(fileName);

                setFileInfos(prev => ({ ...prev, [fileName]: { loading: true } }));

                client.get<EnergyDetail>(`/energy/${fileName}`)
                    .then(res => {
                        if (isMounted) {
                            setFileInfos(prev => ({
                                ...prev,
                                [fileName]: {
                                    energy_class: res.data.energy_class,
                                    annual_cost_estimate: res.data.annual_cost_estimate,
                                    loading: false
                                }
                            }));
                        }
                    })
                    .catch(() => {
                        if (isMounted) {
                            setFileInfos(prev => ({
                                ...prev,
                                [fileName]: { loading: false }
                            }));
                        }
                    });
            }
        });

        return () => {
            isMounted = false;
        };
    }, [files]);

    return (
        <div className="mt-3 pt-3 border-t border-white/10">
            <div className="flex items-center gap-1.5 mb-2">
                <FileCheck className="w-3 h-3 text-green-400" />
                <span className="text-[10px] uppercase text-gray-500 font-medium">Energy certificates ({files.length})</span>
            </div>
            <div className="space-y-1.5">
                {displayedFiles.map((file, index) => {
                    const fileName = getFileName(file);
                    const info = fileInfos[fileName];
                    return (
                        <button
                            key={index}
                            onClick={() => onFileClick(file)}
                            className="w-full flex items-center gap-2 px-2 py-2 rounded bg-white/5 hover:bg-emerald-500/10 text-xs text-gray-400 hover:text-emerald-400 transition-colors text-left group"
                        >
                            <FileText className="w-3 h-3 text-gray-500 group-hover:text-emerald-400 shrink-0" />
                            <span className="truncate flex-1 min-w-0">
                                {fileName.replace(/\.xml$/i, '').split('_')[1] || fileName.replace(/\.xml$/i, '')}
                            </span>
                            {/* Badges for Energy Class and Cost */}
                            <div className="flex items-center gap-1.5 shrink-0">
                                {info?.loading ? (
                                    <span className="w-3 h-3 border border-gray-500/50 border-t-emerald-400 rounded-full animate-spin" />
                                ) : (
                                    <>
                                        {info?.energy_class && (
                                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${getClassBadgeColor(info.energy_class)}`}>
                                                {info.energy_class}
                                            </span>
                                        )}
                                        {info?.annual_cost_estimate != null && (
                                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-400 border border-purple-500/30">
                                                €{info.annual_cost_estimate.toLocaleString('it-IT', { maximumFractionDigits: 0 })}
                                            </span>
                                        )}
                                    </>
                                )}
                            </div>
                        </button>
                    );
                })}
            </div>
            {hasMore && (
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="mt-2 flex items-center gap-1 text-[10px] text-emerald-400 hover:text-emerald-300 transition-colors"
                >
                    <ChevronDown className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                    {isExpanded ? 'Show less' : `Show matching ${files.length - 2}`}
                </button>
            )}
        </div>
    );
};


export const BuildingDetail: React.FC<BuildingDetailProps> = ({ data, runId, onFeedbackSuccess }) => {
    const details = data;
    const [selectedEnergyFile, setSelectedEnergyFile] = useState<string | null>(null);
    const [existingFeedback, setExistingFeedback] = useState<AgentFeedbackResponse | undefined>(undefined);

    const is_meta_building_val = details.is_meta_building === true || String(details.is_meta_building) === 'true';

    // Fetch existing feedback when building or run changes
    useEffect(() => {
        if (runId && details.id) {
            feedbackApi.getBuildingFeedback(runId, details.id)
                .then(feedbacks => {
                    if (feedbacks && feedbacks.length > 0) {
                        // Use the most recent feedback
                        setExistingFeedback(feedbacks[0]);
                    } else {
                        setExistingFeedback(undefined);
                    }
                })
                .catch(err => console.error("Error loading building feedback:", err));
        } else {
            setExistingFeedback(undefined);
        }
    }, [runId, details.id]);

    // Proximity Radar data (6 metrics)
    const proximityRadarData = useMemo(() => {
        if (!details.proximity_scores) return [];
        return [
            { subject: 'Healthcare', A: details.proximity_scores.healthcare || 0, fullMark: 5 },
            { subject: 'Mobility', A: details.proximity_scores.mobility || 0, fullMark: 5 },
            { subject: 'Greenery', A: details.proximity_scores.greenery || 0, fullMark: 5 },
            { subject: 'Sport', A: details.proximity_scores.sport || 0, fullMark: 5 },
            { subject: 'Commerce', A: details.proximity_scores.commerce || 0, fullMark: 5 },
            { subject: 'Education', A: details.proximity_scores.education || 0, fullMark: 5 },
        ];
    }, [details.proximity_scores]);

    // Energy Radar data
    const energyRadarData = useMemo(() => {
        if (!details.energy_scores) return [];
        return [
            { subject: 'Class', A: details.energy_scores.class_score || 0, fullMark: 5 },
            { subject: 'Plant', A: details.energy_scores.plant_score || 0, fullMark: 5 },
            { subject: 'Envelope', A: details.energy_scores.envelope_score || 0, fullMark: 5 },
            { subject: 'Renewable', A: details.energy_scores.renewables_score || 0, fullMark: 5 },
        ];
    }, [details.energy_scores]);

    // Custom tick component for radar chart to show values
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const renderPolarAngleAxisTick = (props: any) => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { payload, x, y, cx, cy, verticalAnchor, ...rest } = props;
        const dataPoint = proximityRadarData.find(d => d.subject === payload.value);
        const value = dataPoint?.A ?? 0;

        return (
            <g>
                <text {...rest} x={x} y={y} fill="#9ca3af" fontSize={9} textAnchor={x > cx ? 'start' : x < cx ? 'end' : 'middle'}>
                    {payload.value}
                </text>
                <text {...rest} x={x} y={y + 10} fill="#10b981" fontSize={8} fontWeight="bold" textAnchor={x > cx ? 'start' : x < cx ? 'end' : 'middle'}>
                    {Math.round(value)}
                </text>
            </g>
        );
    };

    // Custom tick for APE radar
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const renderEnergyRadarTick = (props: any) => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { payload, x, y, cx, cy, verticalAnchor, ...rest } = props;
        const dataPoint = energyRadarData.find(d => d.subject === payload.value);
        const value = dataPoint?.A ?? 0;

        return (
            <g>
                <text {...rest} x={x} y={y} fill="#9ca3af" fontSize={9} textAnchor={x > cx ? 'start' : x < cx ? 'end' : 'middle'}>
                    {payload.value}
                </text>
                <text {...rest} x={x} y={y + 10} fill="#f59e0b" fontSize={8} fontWeight="bold" textAnchor={x > cx ? 'start' : x < cx ? 'end' : 'middle'}>
                    {value}
                </text>
            </g>
        );
    };

    // Energy class color based on class
    const getEnergyColor = (cls?: string) => {
        if (!cls) return 'from-gray-500 to-gray-600';
        if (['A1', 'A2', 'A3', 'A4', 'A'].includes(cls.toUpperCase())) return 'from-emerald-500 to-green-600';
        if (['B', 'C'].includes(cls.toUpperCase())) return 'from-lime-500 to-green-500';
        if (['D', 'E'].includes(cls.toUpperCase())) return 'from-yellow-500 to-orange-500';
        return 'from-red-500 to-orange-600';
    };

    const hasProximityData = proximityRadarData.some(d => d.A > 0);
    const hasEnergyRadarData = energyRadarData.length > 0 && energyRadarData.some(d => d.A > 0);
    const hasAIEvaluation = details.is_evaluated && (details.ranking_score != null || details.evaluation_text);

    // Get tier badge info
    const getTierBadge = () => {
        if (details.tier === 3) {
            return {
                label: 'Top Pick',
                icon: <Sparkles className="w-3 h-3" />,
                className: 'bg-gradient-to-r from-amber-500 to-yellow-500 text-black',
            };
        }
        if (details.tier === 2) {
            return {
                label: 'Result',
                icon: null,
                className: 'bg-emerald-500/20 text-emerald-400 border border-emerald-400/30',
            };
        }
        return null;
    };
    const tierBadge = getTierBadge();

    return (
        <div className="space-y-4 text-gray-200 overflow-y-auto">
            {/* Header with Street Image */}
            <div className="h-28 w-full rounded-xl relative overflow-hidden border border-white/5">
                <StreetImage
                    lat={details.lat}
                    lng={details.lng}
                    buildingId={details.id}
                    className="h-full w-full"
                />
                <div className="absolute bottom-2 left-2 bg-black/80 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/20 shadow-lg">
                    <p className="text-xs font-bold text-white">ID: {details.id}</p>
                </div>
                {/* Tier Badge */}
                {tierBadge && (
                    <div className={`absolute top - 2 left - 2 px - 2.5 py - 1 rounded - lg flex items - center gap - 1.5 text - [10px] font - bold shadow - lg ${tierBadge.className} `}>
                        {tierBadge.icon}
                        {tierBadge.label}
                    </div>
                )}
                {is_meta_building_val && (
                    <div className="absolute top-2 right-2 flex flex-col items-end gap-1">
                        {details.omi_zone && (
                            <div className="bg-emerald-900/90 backdrop-blur-md px-2 py-0.5 rounded border border-emerald-400/50 shadow-lg">
                                <p className="text-[10px] font-semibold text-emerald-200">OMI Zone: {details.omi_zone}</p>
                            </div>
                        )}
                        <div className="bg-purple-900/90 backdrop-blur-md px-2 py-0.5 rounded border border-purple-400/50 shadow-lg">
                            <p className="text-[10px] font-bold text-purple-200">META PROPERTY</p>
                        </div>
                    </div>
                )}
                {!is_meta_building_val && details.omi_zone && (
                    <div className="absolute top-2 right-2 bg-emerald-900/90 backdrop-blur-md px-2 py-0.5 rounded border border-emerald-400/50 shadow-lg">
                        <p className="text-[10px] font-semibold text-emerald-200">OMI Zone: {details.omi_zone}</p>
                    </div>
                )}
            </div>

            {/* Title & Address */}
            <div>
                <h2 className="text-base font-bold text-white leading-tight">
                    {details.address || `Property ${details.id}`}
                </h2>
                {details.city && <p className="text-gray-400 text-xs mt-0.5">{details.city}</p>}
                {details.price && details.price > 0 ? (
                    <p className="text-lg font-bold text-emerald-400 mt-1">
                        € {details.price.toLocaleString('it-IT')} <span className="text-xs font-normal text-gray-400">/year</span>
                    </p>
                ) : details.annual_rent && details.annual_rent > 0 && (
                    <p className="text-lg font-bold text-emerald-400 mt-1">
                        € {details.annual_rent.toLocaleString('it-IT')} <span className="text-xs font-normal text-gray-400">/year (Rent)</span>
                    </p>
                )}
            </div>

            {/* Google Maps Link - Prominent at top */}
            {details.lat && details.lng && (
                <a
                    href={`https://www.google.com/maps?q=${details.lat},${details.lng}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full flex items-center justify-center gap-2 bg-linear-to-r from-emerald-600 to-green-500 hover:from-emerald-500 hover:to-green-400 rounded-lg py-2.5 px-4 text-sm font-medium text-white shadow-lg shadow-emerald-500/20 transition-all"
                >
                    <MapPin className="w-4 h-4" />
                    Open in Google Maps
                </a>
            )}

            {/* User Feedback/Rating */}
            {runId && (
                <div className="flex justify-end">
                    <FeedbackPanel
                        runId={runId}
                        buildingId={details.id}
                        align="right"
                        existingFeedback={existingFeedback ? {
                            id: existingFeedback.id,
                            rating: existingFeedback.rating,
                            comment: existingFeedback.comment
                        } : undefined}
                        onSubmitSuccess={() => {
                            // Refresh feedback to update UI state if needed
                            if (runId && details.id) {
                                feedbackApi.getBuildingFeedback(runId, details.id)
                                    .then(feedbacks => {
                                        if (feedbacks && feedbacks.length > 0) setExistingFeedback(feedbacks[0]);
                                    });
                            }
                            onFeedbackSuccess?.();
                        }}
                    />
                </div>
            )}

            {/* AI Evaluation Card - Show prominently for evaluated buildings */}
            {
                hasAIEvaluation && (
                    <AIEvaluationCard
                        score={details.ranking_score}
                        evaluationText={details.evaluation_text}
                        pros={details.pros}
                        cons={details.cons}
                        compact={false}
                    />
                )
            }

            {/* Property Type & Usage */}
            {
                (details.property_type || details.description) && (
                    <div className="bg-white/5 p-3 rounded-lg border border-white/5 space-y-1">
                        <div className="flex items-center gap-1.5 mb-1">
                            <Building2 className="w-3.5 h-3.5 text-gray-400" />
                            <span className="text-[10px] uppercase text-gray-500 font-medium">Type & Usage</span>
                        </div>
                        {details.property_type && (
                            <p className="text-xs text-gray-300">{details.property_type}</p>
                        )}
                        {details.description && (
                            <p className="text-xs text-gray-400">{details.description}</p>
                        )}
                    </div>
                )
            }

            {/* Key Stats Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                    <p className="text-[9px] text-gray-500 uppercase">Surface</p>
                    <p className="font-semibold text-white">{details.surface_area ? `${details.surface_area} m²` : 'N/A'}</p>
                </div>
                <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                    <p className="text-[9px] text-gray-500 uppercase">Period</p>
                    <p className="font-semibold text-white">{details.construction_year || 'N/A'}</p>
                </div>
            </div>

            {/* Cadastral & Legal Info */}
            <div className="bg-[#1a1d24]/60 p-3 rounded-lg border border-white/5">
                <div className="flex items-center gap-1.5 mb-2">
                    <FileText className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] uppercase text-gray-500 font-medium">Cadastral & Legal Data</span>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    {details.cadastral_sheet && details.cadastral_sheet !== 'None' && (
                        <div className="flex justify-between">
                            <span className="text-gray-500">Sheet</span>
                            <span className="text-gray-300">{details.cadastral_sheet}</span>
                        </div>
                    )}
                    {details.cadastral_parcel && details.cadastral_parcel !== 'None' && (
                        <div className="flex justify-between">
                            <span className="text-gray-500">Parcel</span>
                            <span className="text-gray-300">{details.cadastral_parcel}</span>
                        </div>
                    )}
                    {details.legal_nature && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Legal Nature</span>
                            <span className="text-gray-300 text-right truncate max-w-[150px]">{details.legal_nature}</span>
                        </div>
                    )}
                    {details.purpose && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Purpose</span>
                            <span className="text-gray-300">{details.purpose}</span>
                        </div>
                    )}
                    {details.third_party_tenure_type && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Tenure</span>
                            <span className="text-gray-300">{details.third_party_tenure_type}</span>
                        </div>
                    )}
                    {details.start_date && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Start Date</span>
                            <span className="text-gray-300">{details.start_date}</span>
                        </div>
                    )}
                    {details.cadastral_units_count && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Cadastral Units</span>
                            <span className="text-gray-300">{details.cadastral_units_count}</span>
                        </div>
                    )}
                </div>
                {details.cultural_constraint && details.cultural_constraint.toLowerCase() !== 'no' && (
                    <div className="mt-2 flex items-center gap-1.5 text-amber-400">
                        <Shield className="w-3.5 h-3.5" />
                        <span className="text-[10px]">Constraint: {details.cultural_constraint}</span>
                    </div>
                )}
            </div>

            {/* Energy Section with integrated files list */}
            {
                details.energy_class && (
                    <div className="bg-[#1a1d24]/60 p-3 rounded-lg border border-white/5">
                        <div className="flex items-center gap-1.5 mb-2">
                            <Zap className="w-3.5 h-3.5 text-yellow-400" />
                            <span className="text-[10px] uppercase text-gray-500 font-medium">Energy Class</span>
                        </div>
                        <div className="flex items-center gap-3 mb-3">
                            <div className={`w-12 h-12 shrink-0 rounded-lg bg-linear-to-br ${getEnergyColor(details.energy_class)} flex flex-col items-center justify-center text-white font-bold border border-white/10`}>
                                <span className="text-lg leading-none">{details.energy_class}</span>
                            </div>
                            {details.energy_scores?.total != null && (
                                <div className="flex flex-col">
                                    <span className="text-[10px] text-gray-500">Total Score</span>
                                    <span className="text-xl font-bold text-white">
                                        {details.energy_scores.total.toFixed(0)} <span className="text-xs text-gray-500 font-normal">/20 points</span>
                                    </span>
                                </div>
                            )}
                        </div>
                        {/* Energy Radar Chart with Info Tooltip */}
                        {hasEnergyRadarData && (
                            <>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-[10px] text-gray-500">Detailed Score</span>
                                    <div className="relative group">
                                        <button className="p-1 rounded-full hover:bg-white/10 transition-colors">
                                            <Info className="w-3.5 h-3.5 text-amber-400" />
                                        </button>
                                        {/* Tooltip */}
                                        <div className="absolute right-0 bottom-full mb-1 w-64 p-3 bg-[#1a1d24] border border-white/20 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                                            <p className="text-xs font-semibold text-white mb-2">Scoring Criteria (Scale 1-5)</p>
                                            <div className="space-y-1.5 text-[10px]">
                                                <div>
                                                    <p className="text-emerald-400 font-medium">Energy Class</p>
                                                    <p className="text-gray-400">A1-A4: 5 • B: 4 • C,D: 3 • E: 2 • F,G: 1</p>
                                                </div>
                                                <div>
                                                    <p className="text-orange-400 font-medium">Plant</p>
                                                    <p className="text-gray-400">Heat Pump/Dist. Heat.: 5 • Condensing: 4 • Other: 2</p>
                                                </div>
                                                <div>
                                                    <p className="text-emerald-400 font-medium">Envelope</p>
                                                    <p className="text-gray-400">High quality: 5 • Medium: 3 • Low: 1</p>
                                                </div>
                                                <div>
                                                    <p className="text-green-400 font-medium">Renewables</p>
                                                    <p className="text-gray-400">Present: 5 • Absent: 2</p>
                                                </div>
                                            </div>
                                            <div className="mt-2 pt-2 border-t border-white/10 text-[10px] text-gray-500">
                                                <p><strong>Total:</strong> Sum of 4 scores (min 6, max 20)</p>
                                                <p><strong>Multi-Energy:</strong> MODE for class, AVERAGE for scores</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                {/* Energy Radar Chart */}
                                <div className="bg-white/5 rounded-xl p-4 border border-white/10 relative h-[300px]">
                                    <h4 className="text-xs font-semibold text-gray-300 mb-2 flex items-center gap-1.5 absolute top-4 left-4 z-10">
                                        <Activity className="w-3.5 h-3.5 text-amber-400" />
                                        Energy Performance
                                    </h4>
                                    <div className="w-full h-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={energyRadarData}>
                                                <PolarGrid stroke="#ffffff20" />
                                                <PolarAngleAxis
                                                    dataKey="subject"
                                                    tick={renderEnergyRadarTick}
                                                />
                                                <PolarRadiusAxis angle={30} domain={[0, 5]} tick={false} axisLine={false} />
                                                <Radar
                                                    name="Energy"
                                                    dataKey="A"
                                                    stroke="#f59e0b"
                                                    strokeWidth={2}
                                                    fill="#f59e0b"
                                                    fillOpacity={0.5}
                                                />
                                            </RadarChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                            </>
                        )}
                        {/* Energy Files integrated here */}
                        {details.energy_files && details.energy_files.length > 0 && (
                            <EnergyFilesList files={details.energy_files} onFileClick={setSelectedEnergyFile} />
                        )}
                    </div>
                )
            }

            {/* Meta Property Sub-Properties List */}
            {
                is_meta_building_val && details.sub_properties && details.sub_properties.length > 0 && (
                    <div className="bg-[#1a1d24]/60 p-3 rounded-lg border border-purple-500/20">
                        <div className="flex items-center gap-1.5 mb-2">
                            <Building2 className="w-3.5 h-3.5 text-purple-400" />
                            <span className="text-[10px] uppercase text-gray-500 font-medium">Component Properties ({details.sub_properties.length})</span>
                        </div>
                        <div className="space-y-1.5 max-h-[180px] overflow-y-auto">
                            {details.sub_properties.map((prop, index) => (
                                <div key={index} className="flex items-center gap-3 px-2 py-1.5 rounded bg-white/5 text-xs">
                                    <div className="flex items-center gap-1">
                                        <span className="text-gray-500">ID:</span>
                                        <span className="text-white font-mono">{prop.id}</span>
                                    </div>
                                    {prop.surface_area != null && (
                                        <div className="flex items-center gap-1">
                                            <span className="text-gray-500">MQ:</span>
                                            <span className="text-emerald-400">{prop.surface_area}</span>
                                        </div>
                                    )}
                                    {prop.property_type && (
                                        <div className="flex items-center gap-1 flex-1 min-w-0">
                                            <span className="text-gray-500">Type:</span>
                                            <span className="text-gray-300 truncate">{prop.property_type}</span>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )
            }

            {/* Proximity Radar Chart */}
            {
                hasProximityData && (
                    <div className="bg-[#1a1d24]/60 p-3 rounded-lg border border-white/5">
                        <div className="flex items-center gap-1.5 mb-1">
                            <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                            <span className="text-[10px] uppercase text-gray-500 font-medium">Proximity Score</span>
                        </div>
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] text-gray-500">Detailed Score</span>
                            <div className="relative group">
                                <button className="p-1 rounded-full hover:bg-white/10 transition-colors" aria-label="Info proximity score">
                                    <Info className="w-3.5 h-3.5 text-emerald-400" />
                                </button>
                                <div className="absolute right-0 bottom-full mb-1 w-64 p-3 bg-[#1a1d24] border border-white/20 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                                    <p className="text-xs font-semibold text-white mb-2">Proximity Scale (1-5) • 1km radius</p>
                                    <div className="space-y-1.5 text-[10px] text-gray-400">
                                        <p><span className="text-emerald-300 font-medium">5</span> = Excellent service coverage</p>
                                        <p><span className="text-emerald-300 font-medium">3</span> = Good coverage</p>
                                        <p><span className="text-emerald-300 font-medium">1</span> = Poor coverage</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="bg-white/5 rounded-xl p-4 border border-white/10 relative h-[300px]">
                            <h4 className="text-xs font-semibold text-gray-300 mb-2 flex items-center gap-1.5 absolute top-4 left-4 z-10">
                                <MapPin className="w-3.5 h-3.5 text-emerald-400" />
                                Proximity Services
                            </h4>
                            <div className="w-full h-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <RadarChart cx="50%" cy="50%" outerRadius="70%" data={proximityRadarData}>
                                        <PolarGrid stroke="#ffffff20" />
                                        <PolarAngleAxis dataKey="subject" tick={renderPolarAngleAxisTick} />
                                        <PolarRadiusAxis angle={30} domain={[0, 5]} tick={false} axisLine={false} />
                                        <Radar
                                            name="Proximity"
                                            dataKey="A"
                                            stroke="#10b981"
                                            strokeWidth={2}
                                            fill="#10b981"
                                            fillOpacity={0.5}
                                        />
                                    </RadarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Energy Detail Modal */}
            <EnergyDetailModal
                filename={selectedEnergyFile || ''}
                isOpen={!!selectedEnergyFile}
                onClose={() => setSelectedEnergyFile(null)}
            />
        </div >
    );
};
