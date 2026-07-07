import React, { useState, useEffect } from 'react';
import { X, Zap, Thermometer, Droplets, Snowflake, Wrench, Calendar, MapPin, Building, Info } from 'lucide-react';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';
import client from '../../api/client';
import { getEnergyCertificateLabel, getEnergyFileName } from '../../utils/energyFiles';

export interface EnergyDetail {
    // Basic identification
    file: string;
    unit?: string;
    address?: string;
    issue_date?: string;

    // Energy class and metrics
    energy_class?: string;
    epglnren?: number;  // Non-renewable global performance
    epglren?: number;   // Renewable global performance
    co2_emissions?: number; // kg CO2/m²/year
    surface_area?: number;

    // Energy vector and services
    energy_vector?: string;
    heating_service?: boolean;  // Has heating
    hot_water_service?: boolean;   // Has hot water
    cooling_service?: boolean;   // Has cooling
    ventilation_service?: boolean;  // Has ventilation
    lighting_service?: boolean;  // Has lighting
    transport_service?: boolean; // Has transport (elevators)

    // Location and building
    city?: string;
    climate_zone?: string;
    construction_year?: string;
    property_type_desc?: string;
    property_type_code?: number;
    usage_type_code?: number;
    floor?: string;

    // Quality indicators
    winter_quality?: string;
    summer_quality?: string;
    renewables_available?: string;

    // Intervention recommendations
    renovation_desc?: string;
    target_energy_class?: string;
    payback_period?: number;

    // Heating system
    heating_system_year?: string;
    heating_system_desc?: string;
    heating_system_type?: string;
    heating_system_epnren?: number;  // Non-renewable EP for heating

    // Hot water system
    hot_water_system_year?: string;
    hot_water_system_desc?: string;
    hot_water_system_type?: string;
    hot_water_system_epnren?: number;  // Non-renewable EP for hot water

    // Cooling system
    cooling_system_year?: string;
    cooling_system_desc?: string;
    cooling_system_type?: string;
    cooling_system_epnren?: number;  // Non-renewable EP for cooling

    // Total consumption
    consumo_kwh_tot?: number;
    total_annual_kwh?: number;

    // Cadastral info
    cadastral_code?: string;
    section?: string;
    sheet?: string;
    parcel?: string;
    subaltern?: string;
    subA?: number;
    subDA?: number;

    // Coordinates
    lat?: number;
    lon?: number;

    // Energy scoring breakdown
    energy_score_class?: number;
    energy_score_system?: number;
    energy_score_envelope?: number;
    energy_score_renewables?: number;
    energy_total_points?: number;
    energy_score?: number; // Percentile score

    // Energy cost analysis (calculated)
    kwh_per_sqm?: number;
    annual_cost_estimate?: number;
    cost_per_sqm_year?: number;
    average_kwh_sqm_comparison?: number;
    usage_type_comparison?: string;
    percentage_difference_comparison?: number;
}

interface EnergyDetailModalProps {
    filename: string;
    isOpen: boolean;
    onClose: () => void;
}

interface EnergyDetailResult {
    fileName: string;
    data: EnergyDetail | null;
    error: string | null;
}

const getClassColor = (cls?: string) => {
    if (!cls) return 'from-gray-500 to-gray-600';
    const c = cls.toUpperCase();
    if (['A1', 'A2', 'A3', 'A4', 'A'].includes(c)) return 'from-emerald-500 to-green-600';
    if (['B'].includes(c)) return 'from-lime-500 to-green-500';
    if (['C'].includes(c)) return 'from-yellow-400 to-lime-500';
    if (['D'].includes(c)) return 'from-yellow-500 to-orange-400';
    if (['E'].includes(c)) return 'from-orange-500 to-red-400';
    if (['F'].includes(c)) return 'from-red-500 to-red-600';
    return 'from-red-600 to-red-700';
};

const getQualityEmoji = (quality?: string) => {
    if (!quality) return '❓';
    const q = quality.toLowerCase();
    if (q.includes('sorridente')) return '😊'; // Smiling
    if (q.includes('basita') || q.includes('neutr')) return '😐'; // Astonished / Neutral
    if (q.includes('triste')) return '😔'; // Sad
    return '❓';
};

const InfoRow: React.FC<{ label: string; value?: string | number | null; unit?: string }> = ({ label, value, unit }) => {
    if (value === null || value === undefined || value === '') return null;
    return (
        <div className="flex justify-between text-xs border-b border-white/5 py-1.5 last:border-0">
            <span className="text-gray-500">{label}</span>
            <span className="text-gray-200 text-right max-w-[60%]">{value}{unit && <span className="text-gray-500 ml-1">{unit}</span>}</span>
        </div>
    );
};

export const EnergyDetailModal: React.FC<EnergyDetailModalProps> = ({ filename, isOpen, onClose }) => {
    const activeFileName = isOpen && filename ? getEnergyFileName(filename) : '';
    const [result, setResult] = useState<EnergyDetailResult>({
        fileName: '',
        data: null,
        error: null,
    });

    const data = result.fileName === activeFileName ? result.data : null;
    const error = result.fileName === activeFileName ? result.error : null;
    const loading = Boolean(isOpen && activeFileName && !data && !error);

    useEffect(() => {
        if (!isOpen || !activeFileName || result.fileName === activeFileName) return;

        let isCancelled = false;

        client.get<EnergyDetail>(`/energy/${encodeURIComponent(activeFileName)}`)
            .then(res => {
                if (isCancelled) return;
                setResult({
                    fileName: activeFileName,
                    data: res.data,
                    error: null,
                });
            })
            .catch(err => {
                if (isCancelled) return;
                setResult({
                    fileName: activeFileName,
                    data: null,
                    error: err.response?.data?.detail || err.response?.data?.error?.message || 'Error loading data',
                });
            });

        return () => {
            isCancelled = true;
        };
    }, [activeFileName, isOpen, result.fileName]);

    if (!isOpen) return null;

    const totalAnnualKwh = data?.total_annual_kwh ?? data?.consumo_kwh_tot;

    return (
        <div className="fixed inset-0 z-1000 flex items-center justify-center p-4" onClick={onClose}>
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
            <div
                className="relative bg-[#0f1218]/95 border border-white/10 rounded-2xl max-w-lg w-full max-h-[85vh] overflow-hidden shadow-2xl"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="sticky top-0 bg-[#0f1218]/95 backdrop-blur-md border-b border-white/10 px-4 py-3 flex items-center justify-between z-10">
                    <div className="flex items-center gap-2">
                        <Zap className="w-4 h-4 text-yellow-400" />
                        <h3 className="text-sm font-semibold text-white">Energy certificate details</h3>
                    </div>
                    <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/10 transition-colors">
                        <X className="w-4 h-4 text-gray-400" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-4 overflow-y-auto max-h-[calc(85vh-56px)] space-y-4">
                    {loading && (
                        <div className="flex items-center justify-center py-12">
                            <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin" />
                        </div>
                    )}

                    {error && (
                        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-center">
                            <p className="text-red-400 text-sm">{error}</p>
                        </div>
                    )}

                    {data && !loading && (
                        <>
                            {/* Energy Class Hero */}
                            <div className="flex items-center gap-4">
                                <div className={`w-16 h-16 rounded-xl bg-linear-to-br ${getClassColor(data.energy_class)} flex items-center justify-center text-2xl font-bold text-white shadow-lg`}>
                                    {data.energy_class || '?'}
                                </div>
                                <div className="flex-1">
                                    <p className="text-white font-medium text-sm truncate">{data.address || 'Address not available'}</p>
                                    <p className="text-gray-500 text-xs">{data.city}</p>
                                    {data.issue_date && (
                                        <p className="text-gray-400 text-xs mt-1 flex items-center gap-1">
                                            <Calendar className="w-3 h-3" />
                                            Issued: {data.issue_date}
                                        </p>
                                    )}
                                </div>
                            </div>

                            {/* Key Metrics - Row 1 */}
                            <div className="grid grid-cols-3 gap-2">
                                <div className="bg-white/5 rounded-lg p-2 text-center">
                                    <p className="text-[10px] text-gray-500 uppercase">EP gl,nren</p>
                                    <p className="text-sm font-semibold text-cyan-400">{data.epglnren?.toFixed(1) || 'N/A'}</p>
                                </div>
                                <div className="bg-white/5 rounded-lg p-2 text-center">
                                    <p className="text-[10px] text-gray-500 uppercase">CO₂</p>
                                    <p className="text-sm font-semibold text-orange-400">{data.co2_emissions?.toFixed(1) || 'N/A'}</p>
                                </div>
                                <div className="bg-white/5 rounded-lg p-2 text-center">
                                    <p className="text-[10px] text-gray-500 uppercase">Surface</p>
                                    <p className="text-sm font-semibold text-white">{data.surface_area?.toFixed(0) || 'N/A'} m²</p>
                                </div>
                            </div>

                            {/* Per m² values - Row 2 */}
                            {(data.kwh_per_sqm || data.cost_per_sqm_year) && (
                                <div className="grid grid-cols-2 gap-2">
                                    {data.kwh_per_sqm && (
                                        <div className="bg-linear-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-3 text-center">
                                            <p className="text-[10px] text-gray-500 uppercase mb-1">Consumption per m²</p>
                                            <p className="text-lg font-bold text-purple-400">
                                                {data.kwh_per_sqm.toFixed(1).replace('.', ',')} <span className="text-xs text-gray-500">kWh/m²</span>
                                            </p>
                                        </div>
                                    )}
                                    {data.cost_per_sqm_year && (
                                        <div className="bg-linear-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-3 text-center">
                                            <p className="text-[10px] text-gray-500 uppercase mb-1">Cost per m²</p>
                                            <p className="text-lg font-bold text-purple-400">
                                                €{data.cost_per_sqm_year.toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                            </p>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Energy Cost Analysis - Row 3 */}
                            {(data.energy_score !== undefined && data.energy_score !== null) || totalAnnualKwh || data.annual_cost_estimate ? (
                                <div className="bg-linear-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-3">
                                    <div className="flex items-center gap-2 mb-3">
                                        <div className="w-6 h-6 rounded-full bg-linear-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                                            <span className="text-white text-[10px] font-bold">⚡</span>
                                        </div>
                                        <p className="text-[10px] uppercase text-purple-400 font-medium">Energy cost analysis</p>
                                    </div>

                                    {/* Score display */}
                                    {data.energy_score !== undefined && data.energy_score !== null && (
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="flex items-center gap-3">
                                                <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold ${data.energy_score >= 70 ? 'bg-emerald-500/20 text-emerald-400' :
                                                    data.energy_score >= 40 ? 'bg-yellow-500/20 text-yellow-400' :
                                                        'bg-red-500/20 text-red-400'
                                                    }`}>
                                                    {data.energy_score}
                                                </div>
                                                <div>
                                                    <p className="text-sm font-medium text-white">Efficiency score</p>
                                                    <p className="text-[10px] text-gray-500">
                                                        {data.energy_score >= 70 ? 'Excellent' :
                                                            data.energy_score >= 40 ? 'Average' : 'Below average'}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Total values grid */}
                                    {(totalAnnualKwh || data.annual_cost_estimate) && (
                                        <div className="grid grid-cols-2 gap-2 mb-3">
                                            {totalAnnualKwh && totalAnnualKwh > 0 && (
                                                <div className="bg-black/20 rounded-lg p-2 text-center">
                                                    <p className="text-[10px] text-gray-500 uppercase">Estimated annual TOTAL consumption</p>
                                                    <p className="text-base font-bold text-yellow-400">
                                                        {totalAnnualKwh.toLocaleString('it-IT', { maximumFractionDigits: 0 })} <span className="text-xs text-gray-500">kWh</span>
                                                    </p>
                                                </div>
                                            )}
                                            {data.annual_cost_estimate && (
                                                <div className="bg-black/20 rounded-lg p-2 text-center">
                                                    <p className="text-[10px] text-gray-500 uppercase">Estimated annual TOTAL cost</p>
                                                    <p className="text-base font-bold text-yellow-400">
                                                        €{data.annual_cost_estimate.toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Comparison */}
                                    {data.average_kwh_sqm_comparison && (
                                        <div className="flex items-center justify-between text-xs border-t border-white/10 pt-2">
                                            <span className="text-gray-500">vs {data.usage_type_comparison || 'Average'}</span>
                                            <span className={`font-medium ${(data.percentage_difference_comparison || 0) < 0 ? 'text-emerald-400' :
                                                (data.percentage_difference_comparison || 0) > 20 ? 'text-red-400' : 'text-yellow-400'
                                                }`}>
                                                {(data.percentage_difference_comparison || 0) > 0 ? '+' : ''}{data.percentage_difference_comparison?.toFixed(1)}%
                                                <span className="text-gray-500 ml-1">
                                                    ({data.average_kwh_sqm_comparison.toFixed(0)} kWh/m²)
                                                </span>
                                            </span>
                                        </div>
                                    )}
                                </div>
                            ) : null}

                            {/* Quality Indicators */}
                            {(data.winter_quality || data.summer_quality) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-gray-500 mb-2">Envelope</p>
                                    <div className="flex gap-4">
                                        {data.winter_quality && (
                                            <div className="flex items-center gap-2">
                                                <Thermometer className="w-3.5 h-3.5 text-orange-400" />
                                                <span className="text-xs text-gray-300">Winter: {getQualityEmoji(data.winter_quality)}</span>
                                            </div>
                                        )}
                                        {data.summer_quality && (
                                            <div className="flex items-center gap-2">
                                                <Snowflake className="w-3.5 h-3.5 text-cyan-400" />
                                                <span className="text-xs text-gray-300">Summer: {getQualityEmoji(data.summer_quality)}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Building Info */}
                            <div className="bg-white/5 rounded-lg p-3">
                                <div className="flex items-center gap-1.5 mb-2">
                                    <Building className="w-3.5 h-3.5 text-gray-400" />
                                    <p className="text-[10px] uppercase text-gray-500">Building</p>
                                </div>
                                <InfoRow label="Type" value={data.property_type_desc} />
                                <InfoRow label="Construction year" value={data.construction_year} />
                                <InfoRow label="Floor" value={data.floor} />
                                <InfoRow label="Energy vector" value={data.energy_vector} />
                                <InfoRow label="Renewable sources" value={data.renewables_available} />
                            </div>

                            {/* Systems Info */}
                            <div className="bg-white/5 rounded-lg p-3">
                                <div className="flex items-center gap-1.5 mb-2">
                                    <Wrench className="w-3.5 h-3.5 text-gray-400" />
                                    <p className="text-[10px] uppercase text-gray-500">Systems</p>
                                </div>
                                {data.heating_system_type && (
                                    <div className="mb-2">
                                        <p className="text-[10px] text-orange-400 flex items-center gap-1"><Thermometer className="w-3 h-3" /> Heating</p>
                                        <p className="text-xs text-gray-300 ml-4">{data.heating_system_type} {data.heating_system_year && `(${data.heating_system_year})`}</p>
                                    </div>
                                )}
                                {data.hot_water_system_type && (
                                    <div className="mb-2">
                                        <p className="text-[10px] text-cyan-400 flex items-center gap-1"><Droplets className="w-3 h-3" /> Hot water (DHW)</p>
                                        <p className="text-xs text-gray-300 ml-4">{data.hot_water_system_type} {data.hot_water_system_year && `(${data.hot_water_system_year})`}</p>
                                    </div>
                                )}
                                {data.cooling_system_type && (
                                    <div>
                                        <p className="text-[10px] text-blue-400 flex items-center gap-1"><Snowflake className="w-3 h-3" /> Cooling</p>
                                        <p className="text-xs text-gray-300 ml-4">{data.cooling_system_type} {data.cooling_system_year && `(${data.cooling_system_year})`}</p>
                                    </div>
                                )}
                            </div>

                            {/* Recommended Intervention */}
                            {data.renovation_desc && (
                                <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-emerald-400 mb-1">Recommended intervention</p>
                                    <p className="text-xs text-gray-300">{data.renovation_desc}</p>
                                    {(data.target_energy_class || data.payback_period) && (
                                        <div className="flex gap-4 mt-2">
                                            {data.target_energy_class && (
                                                <span className="text-xs text-emerald-400">Target: Class {data.target_energy_class}</span>
                                            )}
                                            {data.payback_period && (
                                                <span className="text-xs text-gray-500">Payback: {data.payback_period} years</span>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Cadastral Info - Enhanced */}
                            {(data.sheet || data.parcel || data.cadastral_code) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <div className="flex items-center gap-1.5 mb-2">
                                        <MapPin className="w-3.5 h-3.5 text-gray-400" />
                                        <p className="text-[10px] uppercase text-gray-500">Cadastral data</p>
                                    </div>
                                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                                        {data.cadastral_code && <span className="text-gray-400">Code: <span className="text-gray-200">{data.cadastral_code}</span></span>}
                                        {data.section && <span className="text-gray-400">Sect.: <span className="text-gray-200">{data.section}</span></span>}
                                        {data.sheet && <span className="text-gray-400">Sheet: <span className="text-gray-200">{data.sheet}</span></span>}
                                        {data.parcel && <span className="text-gray-400">Parcel: <span className="text-gray-200">{data.parcel}</span></span>}
                                        {data.subaltern && <span className="text-gray-400">Sub.: <span className="text-gray-200">{data.subaltern}</span></span>}
                                    </div>
                                </div>
                            )}

                            {/* Services Available */}
                            {(data.heating_service !== undefined || data.hot_water_service !== undefined || data.cooling_service !== undefined) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-gray-500 mb-2">Energy Services</p>
                                    <div className="flex flex-wrap gap-2">
                                        <span className={`px-2 py-1 rounded text-xs ${data.heating_service ? 'bg-orange-500/20 text-orange-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                            <Thermometer className="w-3 h-3 inline mr-1" />Heating
                                        </span>
                                        <span className={`px-2 py-1 rounded text-xs ${data.hot_water_service ? 'bg-cyan-500/20 text-cyan-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                            <Droplets className="w-3 h-3 inline mr-1" />Hot Water
                                        </span>
                                        <span className={`px-2 py-1 rounded text-xs ${data.cooling_service ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                            <Snowflake className="w-3 h-3 inline mr-1" />Cooling
                                        </span>
                                        {data.ventilation_service !== undefined && (
                                            <span className={`px-2 py-1 rounded text-xs ${data.ventilation_service ? 'bg-purple-500/20 text-purple-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                                Ventilation
                                            </span>
                                        )}
                                        {data.lighting_service !== undefined && (
                                            <span className={`px-2 py-1 rounded text-xs ${data.lighting_service ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                                Lighting
                                            </span>
                                        )}
                                        {data.transport_service !== undefined && (
                                            <span className={`px-2 py-1 rounded text-xs ${data.transport_service ? 'bg-pink-500/20 text-pink-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                                Transport
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Energy Scoring Breakdown */}
                            {data.energy_total_points !== undefined && (
                                <div className="bg-linear-to-r from-blue-500/10 to-cyan-500/10 border border-blue-500/20 rounded-lg p-3">
                                    <div className="flex items-center justify-between mb-2">
                                        <p className="text-[10px] uppercase text-blue-400">Detailed energy score</p>
                                        <div className="relative group">
                                            <button className="p-1 rounded-full hover:bg-white/10 transition-colors">
                                                <Info className="w-4 h-4 text-blue-400" />
                                            </button>
                                            {/* Tooltip */}
                                            <div className="absolute right-0 top-full mt-1 w-72 p-3 bg-[#1a1d24] border border-white/20 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                                                <p className="text-xs font-semibold text-white mb-2">Scoring criteria (Scale 1-5)</p>
                                                <div className="space-y-2 text-[10px]">
                                                    <div>
                                                        <p className="text-emerald-400 font-medium">Energy class</p>
                                                        <p className="text-gray-400">A1-A4: 5 • B: 4 • C,D: 3 • E: 2 • F,G: 1</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-orange-400 font-medium">Plant</p>
                                                        <p className="text-gray-400">Heat pump/Dist. heat.: 5 • Condensing/Biomass: 4 • Other: 2</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-cyan-400 font-medium">Envelope</p>
                                                        <p className="text-gray-400">High quality: 5 • Medium: 3 • Low: 1</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-green-400 font-medium">Renewables</p>
                                                        <p className="text-gray-400">Present: 5 • Absent: 2</p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Radar Chart */}
                                    {(() => {
                                        const radarData = [
                                            { subject: 'Class', A: data.energy_score_class || 0, fullMark: 5 },
                                            { subject: 'Plant', A: data.energy_score_system || 0, fullMark: 5 },
                                            { subject: 'Envelope', A: data.energy_score_envelope || 0, fullMark: 5 },
                                            { subject: 'Renewable', A: data.energy_score_renewables || 0, fullMark: 5 },
                                        ];

                                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                        const renderTick = (props: any) => {
                                            const { payload, x, y, cx, ...rest } = props;
                                            const dataPoint = radarData.find(d => d.subject === payload.value);
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

                                        return (
                                            <div className="w-full h-[160px]">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <RadarChart cx="50%" cy="50%" outerRadius="65%" data={radarData}>
                                                        <PolarGrid stroke="rgba(255,255,255,0.08)" />
                                                        <PolarAngleAxis dataKey="subject" tick={renderTick} />
                                                        <PolarRadiusAxis angle={45} domain={[0, 5]} tick={false} axisLine={false} />
                                                        <Radar name="Score" dataKey="A" stroke="#f59e0b" strokeWidth={2} fill="#f59e0b" fillOpacity={0.35} />
                                                    </RadarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        );
                                    })()}

                                    <div className="mt-2 pt-2 border-t border-white/10 flex justify-between items-center">
                                        <span className="text-xs text-gray-400">Total score</span>
                                        <span className="text-lg font-bold text-white">{data.energy_total_points} <span className="text-xs text-gray-500">/20 points</span></span>
                                    </div>
                                </div>
                            )}

                            {/* EP per System */}
                            {(data.heating_system_epnren || data.hot_water_system_epnren || data.cooling_system_epnren) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-gray-500 mb-2">Non-renewable EP per service</p>
                                    <div className="space-y-1">
                                        {data.heating_system_epnren && (
                                            <div className="flex justify-between text-xs">
                                                <span className="text-orange-400"><Thermometer className="w-3 h-3 inline mr-1" />Heating</span>
                                                <span className="text-gray-200">{data.heating_system_epnren.toFixed(2)} kWh/m²</span>
                                            </div>
                                        )}
                                        {data.hot_water_system_epnren && (
                                            <div className="flex justify-between text-xs">
                                                <span className="text-cyan-400"><Droplets className="w-3 h-3 inline mr-1" />Hot water (DHW)</span>
                                                <span className="text-gray-200">{data.hot_water_system_epnren.toFixed(2)} kWh/m²</span>
                                            </div>
                                        )}
                                        {data.cooling_system_epnren && (
                                            <div className="flex justify-between text-xs">
                                                <span className="text-blue-400"><Snowflake className="w-3 h-3 inline mr-1" />Cooling</span>
                                                <span className="text-gray-200">{data.cooling_system_epnren.toFixed(2)} kWh/m²</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Coordinates with Google Maps link */}
                            {data.lat && data.lon && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-[10px] uppercase text-gray-500">Coordinates</p>
                                            <p className="text-xs text-gray-300">{data.lat.toFixed(6)}, {data.lon.toFixed(6)}</p>
                                        </div>
                                        <a
                                            href={`https://www.google.com/maps?q=${data.lat},${data.lon}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded text-xs hover:bg-blue-500/30 transition-colors"
                                        >
                                            Open map
                                        </a>
                                    </div>
                                </div>
                            )}

                            {/* File identifier */}
                            <p className="text-[10px] text-gray-600 text-center mt-2">
                                {getEnergyCertificateLabel(data.file)}
                            </p>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};
