import React, { useState, useEffect } from 'react';
import { X, Zap, Thermometer, Droplets, Snowflake, Wrench, Calendar, MapPin, Building } from 'lucide-react';
import client from '../../api/client';

interface APEDetail {
    // Basic identification
    file: string;
    unita?: string;
    indirizzo?: string;
    data_emissione?: string;

    // Energy class and metrics
    classe?: string;
    epglnren?: number;  // EP globale non rinnovabile
    epglren?: number;   // EP globale rinnovabile
    co2?: number;       // kg CO2/m²/anno
    superficie?: number;

    // Energy vector and services
    vettore?: string;
    serv_risc?: boolean;  // Has heating
    serv_acs?: boolean;   // Has hot water
    serv_raf?: boolean;   // Has cooling
    serv_vent?: boolean;  // Has ventilation
    serv_illu?: boolean;  // Has lighting
    serv_trasp?: boolean; // Has transport (elevators)

    // Location and building
    comune?: string;
    zona_climatica?: string;
    anno_costruzione?: string;
    tipologia_edilizia_str?: string;
    tipologia_edilizia_cod?: number;
    destinazione_uso_cod?: number;
    piano?: string;

    // Quality indicators
    qualita_invernale?: string;
    qualita_estiva?: string;
    fonti_rinnovabili?: string;

    // Intervention recommendations
    intervento_desc?: string;
    intervento_classe_target?: string;
    intervento_payback?: number;

    // Heating system
    imp_risc_anno?: string;
    imp_risc_desc?: string;
    imp_risc_tipo?: string;
    imp_risc_epnren?: number;  // EP non rinnovabile riscaldamento

    // Hot water system
    imp_acs_anno?: string;
    imp_acs_desc?: string;
    imp_acs_tipo?: string;
    imp_acs_epnren?: number;  // EP non rinnovabile ACS

    // Cooling system
    imp_raf_anno?: string;
    imp_raf_desc?: string;
    imp_raf_tipo?: string;
    imp_raf_epnren?: number;  // EP non rinnovabile raffrescamento

    // Total consumption
    consumo_kwh_tot?: number;

    // Cadastral info (complete)
    codice_catastale?: string;
    sezione?: string;
    foglio?: string;
    particella?: string;
    subalterno?: string;
    subA?: number;
    subDA?: number;

    // Coordinates
    lat?: number;
    lon?: number;

    // APE scoring breakdown
    ape_class_score?: number;
    ape_system_score?: number;
    ape_envelope_score?: number;
    ape_renewables_score?: number;
    ape_total_points?: number;
    ape_score?: number;

    // Energy cost analysis (calculated)
    energy_score?: number;
    kwh_per_sqm?: number;
    costo_annuo_euro?: number;
    costo_per_mq_anno?: number;
    confronto_media_kwh_mq?: number;
    confronto_tipo_uso?: string;
    confronto_differenza_pct?: number;
}

interface APEDetailModalProps {
    filename: string;
    isOpen: boolean;
    onClose: () => void;
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
    if (q.includes('sorridente')) return '😊';
    if (q.includes('basita') || q.includes('neutr')) return '😐';
    if (q.includes('triste')) return '😔';
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

export const APEDetailModal: React.FC<APEDetailModalProps> = ({ filename, isOpen, onClose }) => {
    const [data, setData] = useState<APEDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!isOpen || !filename) return;

        setLoading(true);
        setError(null);

        client.get<APEDetail>(`/ape/${encodeURIComponent(filename)}`)
            .then(res => {
                setData(res.data);
                setLoading(false);
            })
            .catch(err => {
                setError(err.response?.data?.detail || 'Errore nel caricamento');
                setLoading(false);
            });
    }, [filename, isOpen]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4" onClick={onClose}>
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
            <div
                className="relative bg-[#0f1218]/95 border border-white/10 rounded-2xl max-w-lg w-full max-h-[85vh] overflow-hidden shadow-2xl"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="sticky top-0 bg-[#0f1218]/95 backdrop-blur-md border-b border-white/10 px-4 py-3 flex items-center justify-between z-10">
                    <div className="flex items-center gap-2">
                        <Zap className="w-4 h-4 text-yellow-400" />
                        <h3 className="text-sm font-semibold text-white">Dettaglio APE</h3>
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
                                <div className={`w-16 h-16 rounded-xl bg-gradient-to-br ${getClassColor(data.classe)} flex items-center justify-center text-2xl font-bold text-white shadow-lg`}>
                                    {data.classe || '?'}
                                </div>
                                <div className="flex-1">
                                    <p className="text-white font-medium text-sm truncate">{data.indirizzo || 'Indirizzo non disponibile'}</p>
                                    <p className="text-gray-500 text-xs">{data.comune}</p>
                                    {data.data_emissione && (
                                        <p className="text-gray-400 text-xs mt-1 flex items-center gap-1">
                                            <Calendar className="w-3 h-3" />
                                            Emesso: {data.data_emissione}
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
                                    <p className="text-sm font-semibold text-orange-400">{data.co2?.toFixed(1) || 'N/A'}</p>
                                </div>
                                <div className="bg-white/5 rounded-lg p-2 text-center">
                                    <p className="text-[10px] text-gray-500 uppercase">Superficie</p>
                                    <p className="text-sm font-semibold text-white">{data.superficie?.toFixed(0) || 'N/A'} m²</p>
                                </div>
                            </div>

                            {/* Per m² values - Row 2 */}
                            {(data.kwh_per_sqm || data.costo_per_mq_anno) && (
                                <div className="grid grid-cols-2 gap-2">
                                    {data.kwh_per_sqm && (
                                        <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-3 text-center">
                                            <p className="text-[10px] text-gray-500 uppercase mb-1">Consumo per m²</p>
                                            <p className="text-lg font-bold text-purple-400">
                                                {data.kwh_per_sqm.toFixed(1).replace('.', ',')} <span className="text-xs text-gray-500">kWh/m²</span>
                                            </p>
                                        </div>
                                    )}
                                    {data.costo_per_mq_anno && (
                                        <div className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-3 text-center">
                                            <p className="text-[10px] text-gray-500 uppercase mb-1">Costo per m²</p>
                                            <p className="text-lg font-bold text-purple-400">
                                                €{data.costo_per_mq_anno.toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                            </p>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Energy Cost Analysis - Row 3 */}
                            {(data.energy_score !== undefined && data.energy_score !== null) || data.consumo_kwh_tot || data.costo_annuo_euro ? (
                                <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg p-3">
                                    <div className="flex items-center gap-2 mb-3">
                                        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                                            <span className="text-white text-[10px] font-bold">⚡</span>
                                        </div>
                                        <p className="text-[10px] uppercase text-purple-400 font-medium">Analisi Costi Energetici</p>
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
                                                    <p className="text-sm font-medium text-white">Score Efficienza</p>
                                                    <p className="text-[10px] text-gray-500">
                                                        {data.energy_score >= 70 ? 'Ottimo' :
                                                            data.energy_score >= 40 ? 'Nella media' : 'Sotto la media'}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Total values grid */}
                                    {(data.consumo_kwh_tot || data.costo_annuo_euro) && (
                                        <div className="grid grid-cols-2 gap-2 mb-3">
                                            {data.consumo_kwh_tot && data.consumo_kwh_tot > 0 && (
                                                <div className="bg-black/20 rounded-lg p-2 text-center">
                                                    <p className="text-[10px] text-gray-500 uppercase">Consumo TOTALE annuo stimato</p>
                                                    <p className="text-base font-bold text-yellow-400">
                                                        {data.consumo_kwh_tot.toLocaleString('it-IT', { maximumFractionDigits: 0 })} <span className="text-xs text-gray-500">kWh</span>
                                                    </p>
                                                </div>
                                            )}
                                            {data.costo_annuo_euro && (
                                                <div className="bg-black/20 rounded-lg p-2 text-center">
                                                    <p className="text-[10px] text-gray-500 uppercase">Costo TOTALE annuo stimato</p>
                                                    <p className="text-base font-bold text-yellow-400">
                                                        €{data.costo_annuo_euro.toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Comparison */}
                                    {data.confronto_media_kwh_mq && (
                                        <div className="flex items-center justify-between text-xs border-t border-white/10 pt-2">
                                            <span className="text-gray-500">vs {data.confronto_tipo_uso || 'Media'}</span>
                                            <span className={`font-medium ${(data.confronto_differenza_pct || 0) < 0 ? 'text-emerald-400' :
                                                (data.confronto_differenza_pct || 0) > 20 ? 'text-red-400' : 'text-yellow-400'
                                                }`}>
                                                {(data.confronto_differenza_pct || 0) > 0 ? '+' : ''}{data.confronto_differenza_pct?.toFixed(1)}%
                                                <span className="text-gray-500 ml-1">
                                                    ({data.confronto_media_kwh_mq.toFixed(0)} kWh/m²)
                                                </span>
                                            </span>
                                        </div>
                                    )}
                                </div>
                            ) : null}

                            {/* Quality Indicators */}
                            {(data.qualita_invernale || data.qualita_estiva) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-gray-500 mb-2">Involucro</p>
                                    <div className="flex gap-4">
                                        {data.qualita_invernale && (
                                            <div className="flex items-center gap-2">
                                                <Thermometer className="w-3.5 h-3.5 text-orange-400" />
                                                <span className="text-xs text-gray-300">Inverno: {getQualityEmoji(data.qualita_invernale)}</span>
                                            </div>
                                        )}
                                        {data.qualita_estiva && (
                                            <div className="flex items-center gap-2">
                                                <Snowflake className="w-3.5 h-3.5 text-cyan-400" />
                                                <span className="text-xs text-gray-300">Estate: {getQualityEmoji(data.qualita_estiva)}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Building Info */}
                            <div className="bg-white/5 rounded-lg p-3">
                                <div className="flex items-center gap-1.5 mb-2">
                                    <Building className="w-3.5 h-3.5 text-gray-400" />
                                    <p className="text-[10px] uppercase text-gray-500">Edificio</p>
                                </div>
                                <InfoRow label="Tipologia" value={data.tipologia_edilizia_str} />
                                <InfoRow label="Anno costruzione" value={data.anno_costruzione} />
                                <InfoRow label="Piano" value={data.piano} />
                                <InfoRow label="Vettore energetico" value={data.vettore} />
                                <InfoRow label="Fonti rinnovabili" value={data.fonti_rinnovabili} />
                            </div>

                            {/* Systems Info */}
                            <div className="bg-white/5 rounded-lg p-3">
                                <div className="flex items-center gap-1.5 mb-2">
                                    <Wrench className="w-3.5 h-3.5 text-gray-400" />
                                    <p className="text-[10px] uppercase text-gray-500">Impianti</p>
                                </div>
                                {data.imp_risc_tipo && (
                                    <div className="mb-2">
                                        <p className="text-[10px] text-orange-400 flex items-center gap-1"><Thermometer className="w-3 h-3" /> Riscaldamento</p>
                                        <p className="text-xs text-gray-300 ml-4">{data.imp_risc_tipo} {data.imp_risc_anno && `(${data.imp_risc_anno})`}</p>
                                    </div>
                                )}
                                {data.imp_acs_tipo && (
                                    <div className="mb-2">
                                        <p className="text-[10px] text-cyan-400 flex items-center gap-1"><Droplets className="w-3 h-3" /> ACS</p>
                                        <p className="text-xs text-gray-300 ml-4">{data.imp_acs_tipo} {data.imp_acs_anno && `(${data.imp_acs_anno})`}</p>
                                    </div>
                                )}
                                {data.imp_raf_tipo && (
                                    <div>
                                        <p className="text-[10px] text-blue-400 flex items-center gap-1"><Snowflake className="w-3 h-3" /> Raffrescamento</p>
                                        <p className="text-xs text-gray-300 ml-4">{data.imp_raf_tipo} {data.imp_raf_anno && `(${data.imp_raf_anno})`}</p>
                                    </div>
                                )}
                            </div>

                            {/* Recommended Intervention */}
                            {data.intervento_desc && (
                                <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-emerald-400 mb-1">Intervento consigliato</p>
                                    <p className="text-xs text-gray-300">{data.intervento_desc}</p>
                                    {(data.intervento_classe_target || data.intervento_payback) && (
                                        <div className="flex gap-4 mt-2">
                                            {data.intervento_classe_target && (
                                                <span className="text-xs text-emerald-400">Target: Classe {data.intervento_classe_target}</span>
                                            )}
                                            {data.intervento_payback && (
                                                <span className="text-xs text-gray-500">Payback: {data.intervento_payback} anni</span>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Cadastral Info - Enhanced */}
                            {(data.foglio || data.particella || data.codice_catastale) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <div className="flex items-center gap-1.5 mb-2">
                                        <MapPin className="w-3.5 h-3.5 text-gray-400" />
                                        <p className="text-[10px] uppercase text-gray-500">Dati catastali</p>
                                    </div>
                                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                                        {data.codice_catastale && <span className="text-gray-400">Cod.: <span className="text-gray-200">{data.codice_catastale}</span></span>}
                                        {data.sezione && <span className="text-gray-400">Sez.: <span className="text-gray-200">{data.sezione}</span></span>}
                                        {data.foglio && <span className="text-gray-400">Foglio: <span className="text-gray-200">{data.foglio}</span></span>}
                                        {data.particella && <span className="text-gray-400">Part.: <span className="text-gray-200">{data.particella}</span></span>}
                                        {data.subalterno && <span className="text-gray-400">Sub.: <span className="text-gray-200">{data.subalterno}</span></span>}
                                    </div>
                                </div>
                            )}

                            {/* Services Available */}
                            {(data.serv_risc !== undefined || data.serv_acs !== undefined || data.serv_raf !== undefined) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-gray-500 mb-2">Servizi Energetici</p>
                                    <div className="flex flex-wrap gap-2">
                                        <span className={`px-2 py-1 rounded text-xs ${data.serv_risc ? 'bg-orange-500/20 text-orange-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                            <Thermometer className="w-3 h-3 inline mr-1" />Riscaldamento
                                        </span>
                                        <span className={`px-2 py-1 rounded text-xs ${data.serv_acs ? 'bg-cyan-500/20 text-cyan-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                            <Droplets className="w-3 h-3 inline mr-1" />ACS
                                        </span>
                                        <span className={`px-2 py-1 rounded text-xs ${data.serv_raf ? 'bg-blue-500/20 text-blue-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                            <Snowflake className="w-3 h-3 inline mr-1" />Raffrescamento
                                        </span>
                                        {data.serv_vent !== undefined && (
                                            <span className={`px-2 py-1 rounded text-xs ${data.serv_vent ? 'bg-purple-500/20 text-purple-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                                Ventilazione
                                            </span>
                                        )}
                                        {data.serv_illu !== undefined && (
                                            <span className={`px-2 py-1 rounded text-xs ${data.serv_illu ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                                Illuminazione
                                            </span>
                                        )}
                                        {data.serv_trasp !== undefined && (
                                            <span className={`px-2 py-1 rounded text-xs ${data.serv_trasp ? 'bg-pink-500/20 text-pink-400' : 'bg-gray-700/50 text-gray-500'}`}>
                                                Trasporto
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* APE Scoring Breakdown */}
                            {data.ape_total_points !== undefined && (
                                <div className="bg-gradient-to-r from-blue-500/10 to-cyan-500/10 border border-blue-500/20 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-blue-400 mb-2">Punteggio APE Dettagliato</p>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="bg-black/20 rounded p-2 text-center">
                                            <p className="text-[10px] text-gray-500">Classe</p>
                                            <p className="text-sm font-bold text-emerald-400">{data.ape_class_score ?? '-'}</p>
                                        </div>
                                        <div className="bg-black/20 rounded p-2 text-center">
                                            <p className="text-[10px] text-gray-500">Impianti</p>
                                            <p className="text-sm font-bold text-orange-400">{data.ape_system_score ?? '-'}</p>
                                        </div>
                                        <div className="bg-black/20 rounded p-2 text-center">
                                            <p className="text-[10px] text-gray-500">Involucro</p>
                                            <p className="text-sm font-bold text-cyan-400">{data.ape_envelope_score ?? '-'}</p>
                                        </div>
                                        <div className="bg-black/20 rounded p-2 text-center">
                                            <p className="text-[10px] text-gray-500">Rinnovabili</p>
                                            <p className="text-sm font-bold text-green-400">{data.ape_renewables_score ?? '-'}</p>
                                        </div>
                                    </div>
                                    <div className="mt-2 pt-2 border-t border-white/10 flex justify-between items-center">
                                        <span className="text-xs text-gray-400">Punteggio Totale</span>
                                        <span className="text-lg font-bold text-white">{data.ape_total_points} <span className="text-xs text-gray-500">punti</span></span>
                                    </div>
                                </div>
                            )}

                            {/* EP per System */}
                            {(data.imp_risc_epnren || data.imp_acs_epnren || data.imp_raf_epnren) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-gray-500 mb-2">EP Non Rinnovabile per Servizio</p>
                                    <div className="space-y-1">
                                        {data.imp_risc_epnren && (
                                            <div className="flex justify-between text-xs">
                                                <span className="text-orange-400"><Thermometer className="w-3 h-3 inline mr-1" />Riscaldamento</span>
                                                <span className="text-gray-200">{data.imp_risc_epnren.toFixed(2)} kWh/m²</span>
                                            </div>
                                        )}
                                        {data.imp_acs_epnren && (
                                            <div className="flex justify-between text-xs">
                                                <span className="text-cyan-400"><Droplets className="w-3 h-3 inline mr-1" />ACS</span>
                                                <span className="text-gray-200">{data.imp_acs_epnren.toFixed(2)} kWh/m²</span>
                                            </div>
                                        )}
                                        {data.imp_raf_epnren && (
                                            <div className="flex justify-between text-xs">
                                                <span className="text-blue-400"><Snowflake className="w-3 h-3 inline mr-1" />Raffrescamento</span>
                                                <span className="text-gray-200">{data.imp_raf_epnren.toFixed(2)} kWh/m²</span>
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
                                            <p className="text-[10px] uppercase text-gray-500">Coordinate</p>
                                            <p className="text-xs text-gray-300">{data.lat.toFixed(6)}, {data.lon.toFixed(6)}</p>
                                        </div>
                                        <a
                                            href={`https://www.google.com/maps?q=${data.lat},${data.lon}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded text-xs hover:bg-blue-500/30 transition-colors"
                                        >
                                            Apri Mappa
                                        </a>
                                    </div>
                                </div>
                            )}

                            {/* File identifier */}
                            <p className="text-[10px] text-gray-600 text-center mt-2">{data.file}</p>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};
