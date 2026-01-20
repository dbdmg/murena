import React, { useState, useEffect } from 'react';
import { X, Zap, Thermometer, Droplets, Snowflake, Wrench, Calendar, MapPin, Building } from 'lucide-react';
import client from '../../api/client';

interface APEDetail {
    file: string;
    unita?: string;
    indirizzo?: string;
    data_emissione?: string;
    classe?: string;
    epglnren?: number;
    epglren?: number;
    co2?: number;
    superficie?: number;
    vettore?: string;
    comune?: string;
    zona_climatica?: string;
    anno_costruzione?: string;
    tipologia_edilizia_str?: string;
    piano?: string;
    qualita_invernale?: string;
    qualita_estiva?: string;
    fonti_rinnovabili?: string;
    intervento_desc?: string;
    intervento_classe_target?: string;
    intervento_payback?: number;
    imp_risc_anno?: string;
    imp_risc_desc?: string;
    imp_risc_tipo?: string;
    imp_acs_anno?: string;
    imp_acs_desc?: string;
    imp_acs_tipo?: string;
    imp_raf_anno?: string;
    imp_raf_desc?: string;
    imp_raf_tipo?: string;
    consumo_kwh_tot?: number;
    foglio?: string;
    particella?: string;
    subalterno?: string;
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

                            {/* Key Metrics */}
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

                            {/* Quality Indicators */}
                            {(data.qualita_invernale || data.qualita_estiva) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <p className="text-[10px] uppercase text-gray-500 mb-2">Comfort</p>
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

                            {/* Cadastral Info */}
                            {(data.foglio || data.particella) && (
                                <div className="bg-white/5 rounded-lg p-3">
                                    <div className="flex items-center gap-1.5 mb-2">
                                        <MapPin className="w-3.5 h-3.5 text-gray-400" />
                                        <p className="text-[10px] uppercase text-gray-500">Dati catastali</p>
                                    </div>
                                    <div className="flex gap-4 text-xs">
                                        {data.foglio && <span className="text-gray-400">Foglio: <span className="text-gray-200">{data.foglio}</span></span>}
                                        {data.particella && <span className="text-gray-400">Part.: <span className="text-gray-200">{data.particella}</span></span>}
                                        {data.subalterno && <span className="text-gray-400">Sub.: <span className="text-gray-200">{data.subalterno}</span></span>}
                                    </div>
                                </div>
                            )}

                            {/* Consumption */}
                            {data.consumo_kwh_tot && data.consumo_kwh_tot > 0 && (
                                <div className="bg-white/5 rounded-lg p-3 text-center">
                                    <p className="text-[10px] uppercase text-gray-500 mb-1">Consumo annuo stimato</p>
                                    <p className="text-lg font-bold text-yellow-400">{data.consumo_kwh_tot.toLocaleString('it-IT')} kWh</p>
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
