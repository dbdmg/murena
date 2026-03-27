import React, { useState } from 'react';
import { X, ChevronDown } from 'lucide-react';
import { Button } from '../common/Button';
import { BuildingDetail } from './BuildingDetail';
import type { MapMarker } from '../../api/types';

interface BuildingSidebarProps {
    isOpen: boolean;
    onClose: () => void;
    selectedBuildings: MapMarker[];
    runId: string | null;
    onFeedbackSuccess?: () => void;
}

export const BuildingSidebar: React.FC<BuildingSidebarProps> = ({
    isOpen,
    onClose,
    selectedBuildings,
    runId,
    onFeedbackSuccess
}) => {
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [prevBuildings, setPrevBuildings] = useState(selectedBuildings);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    // Reset selection when buildings change (render-time update)
    if (selectedBuildings !== prevBuildings) {
        setPrevBuildings(selectedBuildings);
        setSelectedIndex(0);
        setIsDropdownOpen(false);
    }

    if (!isOpen) return null;

    const hasMultiple = selectedBuildings.length > 1;
    const currentBuilding = selectedBuildings[selectedIndex];

    return (
        <div className="absolute top-0 right-0 h-full w-[380px] bg-[#1a1d24]/95 backdrop-blur-xl border-l border-white/10 shadow-2xl z-500 flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-white/5 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <span className="font-bold text-gray-200">Property Details</span>
                    {hasMultiple && (
                        <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full">
                            {selectedBuildings.length} at this location
                        </span>
                    )}
                </div>
                <Button variant="ghost" size="sm" onClick={onClose} className="hover:bg-white/5 text-gray-400 hover:text-white">
                    <X className="w-5 h-5" />
                </Button>
            </div>

            {/* Building Selector Dropdown (for multiple buildings at same location) */}
            {hasMultiple && (
                <div className="p-3 border-b border-white/5 shrink-0">
                    <div className="relative">
                        <button
                            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                            className="w-full flex items-center justify-between bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-200 transition-colors"
                        >
                            <span className="truncate">
                                {currentBuilding?.address || `Property ${currentBuilding?.id}`}
                            </span>
                            <ChevronDown className={`w-4 h-4 ml-2 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
                        </button>

                        {isDropdownOpen && (
                            <div className="absolute top-full left-0 right-0 mt-1 bg-[#1a1d24] border border-white/10 rounded-lg shadow-xl z-10 max-h-[200px] overflow-auto">
                                {selectedBuildings.map((building, index) => (
                                    <button
                                        key={building.id}
                                        onClick={() => {
                                            setSelectedIndex(index);
                                            setIsDropdownOpen(false);
                                        }}
                                        className={`w-full text-left px-3 py-2 text-sm hover:bg-white/10 transition-colors ${index === selectedIndex ? 'bg-emerald-500/20 text-emerald-400' : 'text-gray-300'
                                            }`}
                                    >
                                        <div className="font-medium truncate">
                                            {building.address || `Property ${building.id}`}
                                        </div>
                                        <div className="text-xs text-gray-500 truncate">
                                            {building.sub_properties && building.sub_properties.length > 0
                                                ? `ID: ${building.id} | Units: ${building.sub_properties.length}`
                                                : `ID: ${building.id} | ${building.surface_area || 'N/A'} m²`
                                            }
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Content Area - Building Detail */}
            <div className="flex-1 overflow-auto p-4 custom-scrollbar">
                {currentBuilding ? (
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    <BuildingDetail data={currentBuilding as unknown as any} runId={runId || undefined} onFeedbackSuccess={onFeedbackSuccess} />
                ) : (
                    <div className="text-center text-gray-500 mt-10">
                        <p>No property selected.</p>
                        <p className="text-sm">Click a marker on the map.</p>
                    </div>
                )}
            </div>
        </div>
    );
};
