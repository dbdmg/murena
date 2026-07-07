
import React, { useState, useRef } from 'react';
import { Layers, Map as MapIcon, ChevronDown, Check } from 'lucide-react';

export interface LayersState {
    showZoneOMI: boolean;
    showMunicipi: boolean;
    activePOICategories: string[];
}

// eslint-disable-next-line react-refresh/only-export-components
export const defaultLayersState: LayersState = {
    showZoneOMI: false,
    showMunicipi: false,
    activePOICategories: [],
};

interface LayersPanelProps {
    layers: LayersState;
    onLayersChange: (layers: LayersState) => void;
}

// Map POI types to their labels (6 main categories)
const POI_LABELS: Record<string, string> = {
    'sanità': 'Healthcare',
    'mobilità': 'Mobility',
    'verde': 'Green areas',
    'sport': 'Sport',
    'commerciale': 'Commercial',
    'educazione': 'Education',
};

const POI_ICONS: Record<string, string> = {
    'sanità': '🏥',
    'mobilità': '🚇',
    'verde': '🌳',
    'sport': '⚽',
    'commerciale': '🛒',
    'educazione': '🎓',
};

export const LayersPanel: React.FC<LayersPanelProps> = ({
    layers,
    onLayersChange,
}) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);

    const toggleZoneOMI = () => {
        onLayersChange({
            ...layers,
            showZoneOMI: !layers.showZoneOMI,
        });
    };

    const toggleMunicipi = () => {
        onLayersChange({
            ...layers,
            showMunicipi: !layers.showMunicipi,
        });
    };

    const togglePOICategory = (category: string) => {
        const isActive = layers.activePOICategories.includes(category);
        const newCategories = isActive
            ? layers.activePOICategories.filter(c => c !== category)
            : [...layers.activePOICategories, category];

        onLayersChange({
            ...layers,
            activePOICategories: newCategories,
        });
    };

    const activeCount = (layers.showZoneOMI ? 1 : 0) + (layers.showMunicipi ? 1 : 0) + layers.activePOICategories.length;

    return (
        <div ref={panelRef} className="relative">
            {/* Header Chip */}
            <div className="bg-[#0a0d12]/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-xl shadow-black/30 p-2 flex items-center gap-2">
                <div className={`px-2 ${activeCount > 0 ? 'text-emerald-400' : 'text-gray-500'}`}>
                    <Layers className="w-4 h-4" />
                </div>

                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className={`
                        flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium
                        transition-all duration-200 border whitespace-nowrap
                        ${isExpanded || activeCount > 0
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50'
                            : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20 hover:bg-white/10'
                        }
                    `}
                >
                    <span className="font-medium">Layers</span>
                    {activeCount > 0 && (
                        <span className="ml-1 bg-emerald-500/30 px-1.5 py-0.5 rounded-full text-[10px]">
                            {activeCount}
                        </span>
                    )}
                    <ChevronDown className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </button>
            </div>

            {/* Dropdown Menu */}
            {isExpanded && (
                <div className="absolute top-full left-0 mt-2 z-50 w-64">
                    <div className="bg-[#0a0d12]/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl shadow-black/50 p-4 space-y-4">

                        {/* Zone OMI Section */}
                        <div className="space-y-2">
                            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Territory</h3>
                            <button
                                onClick={toggleZoneOMI}
                                className={`
                                    w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all border
                                    ${layers.showZoneOMI
                                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50'
                                        : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'
                                    }
                                `}
                            >
                                <div className="flex items-center gap-2">
                                    <MapIcon className="w-4 h-4" />
                                    <span>Zone OMI</span>
                                </div>
                                {layers.showZoneOMI && <Check className="w-3.5 h-3.5" />}
                            </button>
                            <button
                                onClick={toggleMunicipi}
                                className={`
                                    w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all border
                                    ${layers.showMunicipi
                                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50'
                                        : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'
                                    }
                                `}
                            >
                                <div className="flex items-center gap-2">
                                    <span>🗺️</span>
                                    <span>Districts</span>
                                </div>
                                {layers.showMunicipi && <Check className="w-3.5 h-3.5" />}
                            </button>
                        </div>

                        {/* POI Section */}
                        <div className="space-y-2">
                            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Points of Interest</h3>
                            <div className="grid grid-cols-1 gap-1.5">
                                {Object.keys(POI_LABELS).map((category) => (
                                    <button
                                        key={category}
                                        onClick={() => togglePOICategory(category)}
                                        className={`
                                            flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all border
                                            ${layers.activePOICategories.includes(category)
                                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50'
                                                : 'bg-white/5 text-gray-400 border-white/10 hover:border-white/20'
                                            }
                                        `}
                                    >
                                        <div className="flex items-center gap-2">
                                            <span>{POI_ICONS[category]}</span>
                                            <span>{POI_LABELS[category]}</span>
                                        </div>
                                        {layers.activePOICategories.includes(category) && <Check className="w-3.5 h-3.5" />}
                                    </button>
                                ))}
                            </div>
                        </div>

                    </div>
                </div>
            )}
        </div>
    );
};
