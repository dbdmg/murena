import React, { useMemo, useState, useEffect } from 'react';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';
import { Zap, MapPin, Building2, FileText, Shield, ChevronDown, FileCheck, Sparkles } from 'lucide-react';
import { APEDetailModal } from './APEDetailModal';
import { AIEvaluationCard } from './AIEvaluationCard';
import { StreetImage } from './StreetImage';
import client from '../../api/client';
import type { MarkerTier } from '../../api/types';

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
    ape_scores?: {
        total?: number;
        class_score?: number;
        system_score?: number;
        envelope_score?: number;
        renewables_score?: number;
    };
    poi_scores?: {
        health?: number;
        mobility?: number;
        green?: number;
        education?: number;
        shopping?: number;
        sport?: number;
    };
    ape_files?: string[];
    // User requested fields
    meta_immobile?: boolean;
    tipo_detenzione_a_terzi?: string;
    canone_annuale?: number;
    data_decorrenza?: string;
    numero_immobili_per_catasto?: number;
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
}

// APE file info cache type
interface ApeFileInfo {
    classe?: string;
    costo_annuo_euro?: number;
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
const ApeFilesList: React.FC<{ files: string[]; onFileClick: (file: string) => void }> = ({ files, onFileClick }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [fileInfos, setFileInfos] = useState<Record<string, ApeFileInfo>>({});
    const displayedFiles = isExpanded ? files : files.slice(0, 2);
    const hasMore = files.length > 2;

    // Extract filename from path for display
    const getFileName = (path: string) => {
        const parts = path.split(/[/\\]/);
        return parts[parts.length - 1] || path;
    };

    // Load APE details for each file
    useEffect(() => {
        files.forEach(file => {
            const fileName = getFileName(file);
            if (!fileInfos[fileName]) {
                setFileInfos(prev => ({ ...prev, [fileName]: { loading: true } }));
                client.get(`/ape/${encodeURIComponent(fileName)}`)
                    .then(res => {
                        setFileInfos(prev => ({
                            ...prev,
                            [fileName]: {
                                classe: res.data.classe,
                                costo_annuo_euro: res.data.costo_annuo_euro,
                                loading: false
                            }
                        }));
                    })
                    .catch(() => {
                        setFileInfos(prev => ({
                            ...prev,
                            [fileName]: { loading: false }
                        }));
                    });
            }
        });
    }, [files]);

    return (
        <div className="mt-3 pt-3 border-t border-white/10">
            <div className="flex items-center gap-1.5 mb-2">
                <FileCheck className="w-3 h-3 text-green-400" />
                <span className="text-[10px] uppercase text-gray-500 font-medium">Attestati APE ({files.length})</span>
            </div>
            <div className="space-y-1.5">
                {displayedFiles.map((file, index) => {
                    const fileName = getFileName(file);
                    const info = fileInfos[fileName];
                    return (
                        <button
                            key={index}
                            onClick={() => onFileClick(file)}
                            className="w-full flex items-center gap-2 px-2 py-2 rounded bg-white/5 hover:bg-cyan-500/10 text-xs text-gray-400 hover:text-cyan-400 transition-colors text-left group"
                        >
                            <FileText className="w-3 h-3 text-gray-500 group-hover:text-cyan-400 shrink-0" />
                            <span className="truncate flex-1 min-w-0">{fileName}</span>
                            {/* Badges for Classe Energetica and Costo */}
                            <div className="flex items-center gap-1.5 shrink-0">
                                {info?.loading ? (
                                    <span className="w-3 h-3 border border-gray-500/50 border-t-cyan-400 rounded-full animate-spin" />
                                ) : (
                                    <>
                                        {info?.classe && (
                                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${getClassBadgeColor(info.classe)}`}>
                                                {info.classe}
                                            </span>
                                        )}
                                        {info?.costo_annuo_euro != null && (
                                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-400 border border-purple-500/30">
                                                €{info.costo_annuo_euro.toLocaleString('it-IT', { maximumFractionDigits: 0 })}
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
                    className="mt-2 flex items-center gap-1 text-[10px] text-cyan-400 hover:text-cyan-300 transition-colors"
                >
                    <ChevronDown className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                    {isExpanded ? 'Mostra meno' : `Mostra altri ${files.length - 2}`}
                </button>
            )}
        </div>
    );
};


export const BuildingDetail: React.FC<BuildingDetailProps> = ({ data }) => {
    const details = data;
    const [selectedApeFile, setSelectedApeFile] = useState<string | null>(null);

    // POI Radar data (6 metrics)
    const poiRadarData = useMemo(() => {
        if (!details.poi_scores) return [];
        return [
            { subject: 'Sanità', A: details.poi_scores.health || 0, fullMark: 10 },
            { subject: 'Mobilità', A: details.poi_scores.mobility || 0, fullMark: 10 },
            { subject: 'Verde', A: details.poi_scores.green || 0, fullMark: 10 },
            { subject: 'Sport', A: details.poi_scores.sport || 0, fullMark: 10 },
            { subject: 'Commercio', A: details.poi_scores.shopping || 0, fullMark: 10 },
            { subject: 'Istruzione', A: details.poi_scores.education || 0, fullMark: 10 },
        ];
    }, [details.poi_scores]);

    // APE Radar data (for new APE radar chart)
    const apeRadarData = useMemo(() => {
        if (!details.ape_scores) return [];
        return [
            { subject: 'Classe', A: details.ape_scores.class_score || 0, fullMark: 5 },
            { subject: 'Impianto', A: details.ape_scores.system_score || 0, fullMark: 5 },
            { subject: 'Involucro', A: details.ape_scores.envelope_score || 0, fullMark: 5 },
            { subject: 'Rinnovabili', A: details.ape_scores.renewables_score || 0, fullMark: 5 },
        ];
    }, [details.ape_scores]);

    // Custom tick component for radar chart to show values
    const renderPolarAngleAxisTick = (props: any) => {
        const { payload, x, y, cx, cy, ...rest } = props;
        const dataPoint = poiRadarData.find(d => d.subject === payload.value);
        const value = dataPoint?.A ?? 0;

        return (
            <g>
                <text {...rest} x={x} y={y} fill="#9ca3af" fontSize={9} textAnchor={x > cx ? 'start' : x < cx ? 'end' : 'middle'}>
                    {payload.value}
                </text>
                <text {...rest} x={x} y={y + 10} fill="#06b6d4" fontSize={8} fontWeight="bold" textAnchor={x > cx ? 'start' : x < cx ? 'end' : 'middle'}>
                    {value.toFixed(1)}
                </text>
            </g>
        );
    };

    // Custom tick for APE radar
    const renderApeRadarTick = (props: any) => {
        const { payload, x, y, cx, cy, ...rest } = props;
        const dataPoint = apeRadarData.find(d => d.subject === payload.value);
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

    // APE color based on class
    const getApeColor = (cls?: string) => {
        if (!cls) return 'from-gray-500 to-gray-600';
        if (['A1', 'A2', 'A3', 'A4', 'A'].includes(cls.toUpperCase())) return 'from-emerald-500 to-green-600';
        if (['B', 'C'].includes(cls.toUpperCase())) return 'from-lime-500 to-green-500';
        if (['D', 'E'].includes(cls.toUpperCase())) return 'from-yellow-500 to-orange-500';
        return 'from-red-500 to-orange-600';
    };

    const hasPoiData = poiRadarData.some(d => d.A > 0);
    const hasApeRadarData = apeRadarData.length > 0 && apeRadarData.some(d => d.A > 0);
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
                label: 'Risultato',
                icon: null,
                className: 'bg-cyan-500/20 text-cyan-400 border border-cyan-400/30',
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
                    <div className={`absolute top-2 left-2 px-2.5 py-1 rounded-lg flex items-center gap-1.5 text-[10px] font-bold shadow-lg ${tierBadge.className}`}>
                        {tierBadge.icon}
                        {tierBadge.label}
                    </div>
                )}
                {(details.meta_immobile === true || details.meta_immobile === 'true' as any) && (
                    <div className="absolute top-2 right-2 flex flex-col items-end gap-1">
                        {details.omi_zone && (
                            <div className="bg-cyan-900/90 backdrop-blur-md px-2 py-0.5 rounded border border-cyan-400/50 shadow-lg">
                                <p className="text-[10px] font-semibold text-cyan-200">Zona OMI: {details.omi_zone}</p>
                            </div>
                        )}
                        <div className="bg-purple-900/90 backdrop-blur-md px-2 py-0.5 rounded border border-purple-400/50 shadow-lg">
                            <p className="text-[10px] font-bold text-purple-200">META IMMOBILE</p>
                        </div>
                    </div>
                )}
                {!((details.meta_immobile === true || details.meta_immobile === 'true' as any)) && details.omi_zone && (
                    <div className="absolute top-2 right-2 bg-cyan-900/90 backdrop-blur-md px-2 py-0.5 rounded border border-cyan-400/50 shadow-lg">
                        <p className="text-[10px] font-semibold text-cyan-200">Zona OMI: {details.omi_zone}</p>
                    </div>
                )}
            </div>

            {/* Title & Address */}
            <div>
                <h2 className="text-base font-bold text-white leading-tight">
                    {details.address || `Immobile ${details.id}`}
                </h2>
                {details.city && <p className="text-gray-400 text-xs mt-0.5">{details.city}</p>}
                {details.price && details.price > 0 ? (
                    <p className="text-lg font-bold text-cyan-400 mt-1">
                        € {details.price.toLocaleString('it-IT')} <span className="text-xs font-normal text-gray-400">/anno</span>
                    </p>
                ) : details.canone_annuale && details.canone_annuale > 0 && (
                    <p className="text-lg font-bold text-cyan-400 mt-1">
                        € {details.canone_annuale.toLocaleString('it-IT')} <span className="text-xs font-normal text-gray-400">/anno (Canone)</span>
                    </p>
                )}
            </div>

            {/* Google Maps Link - Prominent at top */}
            {details.lat && details.lng && (
                <a
                    href={`https://www.google.com/maps?q=${details.lat},${details.lng}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full flex items-center justify-center gap-2 bg-linear-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 rounded-lg py-2.5 px-4 text-sm font-medium text-white shadow-lg shadow-blue-500/20 transition-all"
                >
                    <MapPin className="w-4 h-4" />
                    Apri in Google Maps
                </a>
            )}

            {/* AI Evaluation Card - Show prominently for evaluated buildings */}
            {hasAIEvaluation && (
                <AIEvaluationCard
                    score={details.ranking_score}
                    evaluationText={details.evaluation_text}
                    pros={details.pros}
                    cons={details.cons}
                    compact={false}
                />
            )}

            {/* Property Type & Usage */}
            {(details.property_type || details.description) && (
                <div className="bg-white/5 p-3 rounded-lg border border-white/5 space-y-1">
                    <div className="flex items-center gap-1.5 mb-1">
                        <Building2 className="w-3.5 h-3.5 text-gray-400" />
                        <span className="text-[10px] uppercase text-gray-500 font-medium">Tipologia & Uso</span>
                    </div>
                    {details.property_type && (
                        <p className="text-xs text-gray-300">{details.property_type}</p>
                    )}
                    {details.description && (
                        <p className="text-xs text-gray-400">{details.description}</p>
                    )}
                </div>
            )}

            {/* Key Stats Grid */}
            <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                    <p className="text-[9px] text-gray-500 uppercase">Superficie</p>
                    <p className="font-semibold text-white">{details.surface_area ? `${details.surface_area} m²` : 'N/A'}</p>
                </div>
                <div className="bg-white/5 p-2 rounded-lg border border-white/5">
                    <p className="text-[9px] text-gray-500 uppercase">Epoca</p>
                    <p className="font-semibold text-white">{details.construction_year || 'N/A'}</p>
                </div>
            </div>

            {/* Cadastral & Legal Info */}
            <div className="bg-[#1a1d24]/60 p-3 rounded-lg border border-white/5">
                <div className="flex items-center gap-1.5 mb-2">
                    <FileText className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] uppercase text-gray-500 font-medium">Dati Catastali & Giuridici</span>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    {details.cadastral_sheet && details.cadastral_sheet !== 'None' && (
                        <div className="flex justify-between">
                            <span className="text-gray-500">Foglio</span>
                            <span className="text-gray-300">{details.cadastral_sheet}</span>
                        </div>
                    )}
                    {details.cadastral_parcel && details.cadastral_parcel !== 'None' && (
                        <div className="flex justify-between">
                            <span className="text-gray-500">Particella</span>
                            <span className="text-gray-300">{details.cadastral_parcel}</span>
                        </div>
                    )}
                    {details.legal_nature && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Natura Giuridica</span>
                            <span className="text-gray-300 text-right truncate max-w-[150px]">{details.legal_nature}</span>
                        </div>
                    )}
                    {details.purpose && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Finalità</span>
                            <span className="text-gray-300">{details.purpose}</span>
                        </div>
                    )}
                    {details.tipo_detenzione_a_terzi && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Detenzione</span>
                            <span className="text-gray-300">{details.tipo_detenzione_a_terzi}</span>
                        </div>
                    )}
                    {details.data_decorrenza && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Decorrenza</span>
                            <span className="text-gray-300">{details.data_decorrenza}</span>
                        </div>
                    )}
                    {details.numero_immobili_per_catasto && (
                        <div className="flex justify-between col-span-2">
                            <span className="text-gray-500">Immobili Catasto</span>
                            <span className="text-gray-300">{details.numero_immobili_per_catasto}</span>
                        </div>
                    )}
                </div>
                {details.cultural_constraint && details.cultural_constraint.toLowerCase() !== 'no' && (
                    <div className="mt-2 flex items-center gap-1.5 text-amber-400">
                        <Shield className="w-3.5 h-3.5" />
                        <span className="text-[10px]">Vincolo: {details.cultural_constraint}</span>
                    </div>
                )}
            </div>

            {/* APE Section with integrated files list */}
            {details.energy_class && (
                <div className="bg-[#1a1d24]/60 p-3 rounded-lg border border-white/5">
                    <div className="flex items-center gap-1.5 mb-2">
                        <Zap className="w-3.5 h-3.5 text-yellow-400" />
                        <span className="text-[10px] uppercase text-gray-500 font-medium">Classe Energetica</span>
                    </div>
                    <div className="flex items-center gap-3 mb-3">
                        <div className={`w-12 h-12 shrink-0 rounded-lg bg-linear-to-br ${getApeColor(details.energy_class)} flex flex-col items-center justify-center text-white font-bold border border-white/10`}>
                            <span className="text-lg leading-none">{details.energy_class}</span>
                        </div>
                        {details.ape_scores?.total != null && (
                            <div className="flex flex-col">
                                <span className="text-[10px] text-gray-500">Score Totale</span>
                                <span className="text-xl font-bold text-white">{details.ape_scores.total.toFixed(1)}</span>
                            </div>
                        )}
                    </div>
                    {/* APE Radar Chart */}
                    {hasApeRadarData && (
                        <div className="w-full h-[160px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart cx="50%" cy="50%" outerRadius="65%" data={apeRadarData}>
                                    <PolarGrid stroke="rgba(255,255,255,0.08)" />
                                    <PolarAngleAxis dataKey="subject" tick={renderApeRadarTick} />
                                    <PolarRadiusAxis angle={45} domain={[0, 5]} tick={false} axisLine={false} />
                                    <Radar name="Score" dataKey="A" stroke="#f59e0b" strokeWidth={2} fill="#f59e0b" fillOpacity={0.35} />
                                </RadarChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                    {/* APE Files integrated here */}
                    {details.ape_files && details.ape_files.length > 0 && (
                        <ApeFilesList files={details.ape_files} onFileClick={setSelectedApeFile} />
                    )}
                </div>
            )}

            {/* Meta Immobile Sub-Properties List */}
            {(details.meta_immobile === true || details.meta_immobile === 'true' as any) && details.sub_properties && details.sub_properties.length > 0 && (
                <div className="bg-[#1a1d24]/60 p-3 rounded-lg border border-purple-500/20">
                    <div className="flex items-center gap-1.5 mb-2">
                        <Building2 className="w-3.5 h-3.5 text-purple-400" />
                        <span className="text-[10px] uppercase text-gray-500 font-medium">Immobili Componenti ({details.sub_properties.length})</span>
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
                                        <span className="text-cyan-400">{prop.surface_area}</span>
                                    </div>
                                )}
                                {prop.property_type && (
                                    <div className="flex items-center gap-1 flex-1 min-w-0">
                                        <span className="text-gray-500">Tipo:</span>
                                        <span className="text-gray-300 truncate">{prop.property_type}</span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* POI Radar Chart */}
            {hasPoiData && (
                <div className="bg-[#1a1d24]/60 p-3 rounded-lg border border-white/5">
                    <div className="flex items-center gap-1.5 mb-1">
                        <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                        <span className="text-[10px] uppercase text-gray-500 font-medium">Score Localizzazione (POI)</span>
                    </div>
                    <div className="w-full h-[200px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <RadarChart cx="50%" cy="50%" outerRadius="60%" data={poiRadarData}>
                                <PolarGrid stroke="rgba(255,255,255,0.08)" />
                                <PolarAngleAxis dataKey="subject" tick={renderPolarAngleAxisTick} />
                                <PolarRadiusAxis angle={30} domain={[0, 10]} tick={false} axisLine={false} />
                                <Radar name="Score" dataKey="A" stroke="#06b6d4" strokeWidth={2} fill="#06b6d4" fillOpacity={0.35} />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* APE Detail Modal */}
            <APEDetailModal
                filename={selectedApeFile || ''}
                isOpen={!!selectedApeFile}
                onClose={() => setSelectedApeFile(null)}
            />
        </div>
    );
};
