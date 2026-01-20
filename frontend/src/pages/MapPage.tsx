import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Map } from '../components/map/Map';
import { BuildingSidebar } from '../components/building/BuildingSidebar';
import { FilterPanel, defaultFilters } from '../components/filters/FilterPanel';
import type { FilterState } from '../components/filters/FilterPanel';
import { LayersPanel, defaultLayersState } from '../components/map/LayersPanel';
import type { LayersState } from '../components/map/LayersPanel';
import { MapRunSelector } from '../components/map/MapRunSelector';
import { ResultsCarousel } from '../components/map/ResultsCarousel';
import { MapLegend } from '../components/map/MapLegend';
import { AgentRefinementHUD } from '../components/agent/AgentRefinementHUD';

import { mapApi } from '../api/endpoints/map';
import { layersApi } from '../api/endpoints/layers';
import type { MapConfig, MapMarker, POI } from '../api/types';
import { Loader2, Sparkles, Building2 } from 'lucide-react';

import { useSettings } from '../contexts/SettingsContext';
import { useMapContext } from '../contexts/MapContext';
import { useIntelligenceMap } from '../hooks/useIntelligenceMap';

export const MapPage: React.FC = () => {
    const { markersLimit } = useSettings();
    const { setMarkersCount, setTotalCount } = useMapContext();

    // Intelligence Map hook
    const {
        allMarkers,
        topPicks,
        searchLocation,
        activeRunId,
        currentQuery,
        isLoading: isLoadingRun,
        history,
        loadRun,
        clearResults,
    } = useIntelligenceMap(markersLimit);

    const [config, setConfig] = useState<MapConfig | null>(null);
    const [overlays, setOverlays] = useState<{ municipi?: any }>({});
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedBuildings, setSelectedBuildings] = useState<MapMarker[]>([]);
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    // Carousel sync state
    const [focusMarkerId, setFocusMarkerId] = useState<string | null>(null);
    const [hoveredMarkerId, setHoveredMarkerId] = useState<string | null>(null);
    const [carouselSelectedId, setCarouselSelectedId] = useState<string | null>(null);

    // Layer state
    const [layers, setLayers] = useState<LayersState>(defaultLayersState);
    const [pois, setPois] = useState<POI[]>([]);
    const [zoneOMIOverlay, setZoneOMIOverlay] = useState<any>(null);

    // Filter state
    const [filters, setFilters] = useState<FilterState>(defaultFilters);

    // Agent Tuner HUD state
    const [isAgentHUDOpen, setIsAgentHUDOpen] = useState(false);

    // Filter markers based on Intelligence Map filters
    const filteredMarkers = useMemo(() => {
        let result = allMarkers;

        // 1. Filter by Energy Class
        if (filters.energyClasses.length > 0) {
            result = result.filter(m => {
                if (!m.energy_class) return false;
                const cls = m.energy_class.toUpperCase();
                return filters.energyClasses.some(f => cls === f || cls.startsWith(f));
            });
        }

        // 2. Filter by Surface Area
        if (filters.minSurface !== null) {
            result = result.filter(m => (m.surface_area || 0) >= filters.minSurface!);
        }
        if (filters.maxSurface !== null) {
            result = result.filter(m => (m.surface_area || 0) <= filters.maxSurface!);
        }

        // 3. Filter by Epoca Costruzione
        if (filters.epocheCostruzione.length > 0) {
            result = result.filter(m => m.construction_year && filters.epocheCostruzione.includes(m.construction_year));
        }

        // 4. Filter by Tipologia Bene
        if (filters.tipologiaBene.length > 0) {
            result = result.filter(m => m.property_type && filters.tipologiaBene.includes(m.property_type));
        }

        // 5. Filter by Utilizzo
        if (filters.utilizzo.length > 0) {
            // Check description or explicit field if added in future
            // Using description/usage text matching for now as per backend logic
            result = result.filter(m => {
                const desc = (m.description || '').toLowerCase();
                return filters.utilizzo.some(u => desc.includes(u.toLowerCase()));
            });
        }

        // 6. Filter by Vincolo
        if (filters.vincolo.length > 0) {
            result = result.filter(m => {
                const vinc = (m.cultural_constraint || '').toLowerCase();
                return filters.vincolo.some(v => vinc.includes(v.toLowerCase()));
            });
        }

        // 7. Filter by Meta Immobile
        if (filters.isMetaImmobile !== null) {
            result = result.filter(m => {
                const isMeta = m.meta_immobile === true || (m.meta_immobile as any) === 'true' || m.meta_building === true;
                return filters.isMetaImmobile ? isMeta : !isMeta;
            });
        }

        // 8. Filter by Natura Bene
        if (filters.naturaBene) {
            result = result.filter(m => m.legal_nature && m.legal_nature.toUpperCase() === filters.naturaBene!.toUpperCase());
        }

        // 9. Intelligence Map Tiers
        if (filters.showOnlyTopPicks) {
            result = result.filter(m => m.tier === 3);
        } else if (filters.showOnlyResults) {
            result = result.filter(m => m.tier === 2 || m.tier === 3);
        }

        return result;
    }, [allMarkers, filters]);

    // Sync marker count to context whenever markers change
    useEffect(() => {
        setMarkersCount(filteredMarkers.length);
        setTotalCount(allMarkers.length);
    }, [allMarkers, filteredMarkers, setMarkersCount, setTotalCount]);

    // Check for run_id in URL on mount
    useEffect(() => {
        const queryParams = new URLSearchParams(location.search);
        const runId = queryParams.get('run_id');
        if (runId && !activeRunId) {
            loadRun(runId);
        }
    }, [loadRun, activeRunId]);

    // Initial load - config and overlays only
    useEffect(() => {
        const fetchInitialData = async () => {
            try {
                setIsLoading(true);
                const [configData, municipiData] = await Promise.all([
                    mapApi.getConfig(),
                    mapApi.getOverlay('municipi')
                ]);

                setConfig(configData);
                setOverlays({ municipi: municipiData });
            } catch (err) {
                console.error("Error loading map config:", err);
                setError("Failed to load map data.");
            } finally {
                setIsLoading(false);
            }
        };

        fetchInitialData();
    }, []);

    // Fetch Zone OMI Only once when toggled
    useEffect(() => {
        if (layers.showZoneOMI && !zoneOMIOverlay) {
            layersApi.getZoneOMI().then(setZoneOMIOverlay).catch(console.error);
        }
    }, [layers.showZoneOMI, zoneOMIOverlay]);

    // Fetch POIs when categories change
    useEffect(() => {
        if (layers.activePOICategories.length > 0) {
            layersApi.getPOIs(layers.activePOICategories, undefined, 1000)
                .then(data => setPois(data.pois))
                .catch(err => console.error("Error fetching POIs:", err));
        } else {
            setPois([]);
        }
    }, [layers.activePOICategories]);

    // Handle marker click from map
    const handleMarkerClick = useCallback((marker: MapMarker) => {
        setSelectedBuildings([marker]);
        setIsSidebarOpen(true);

        // If it's a top pick, sync with carousel
        if (marker.tier === 3) {
            setCarouselSelectedId(marker.id);
        }
    }, []);

    // Handle cluster click
    const handleClusterClick = useCallback((clusterMarkers: MapMarker[]) => {
        setSelectedBuildings(clusterMarkers);
        setIsSidebarOpen(true);
    }, []);

    // Handle carousel card click - bidirectional sync
    const handleCarouselCardClick = useCallback((marker: MapMarker) => {
        setSelectedBuildings([marker]);
        setIsSidebarOpen(true);
        setCarouselSelectedId(marker.id);
        setFocusMarkerId(marker.id);

        // Reset focus after animation
        setTimeout(() => setFocusMarkerId(null), 1000);
    }, []);

    // Handle carousel hover
    const handleCarouselHover = useCallback((markerId: string | null) => {
        setHoveredMarkerId(markerId);
    }, []);

    // Handle run selection from dropdown
    const handleSelectRun = useCallback((runId: string) => {
        loadRun(runId);
        // Update URL without reload
        const url = new URL(window.location.href);
        url.searchParams.set('run_id', runId);
        window.history.pushState({}, '', url.toString());
    }, [loadRun]);

    // Handle clear results
    const handleClearResults = useCallback(() => {
        clearResults();
        setCarouselSelectedId(null);
        // Remove run_id from URL
        const url = new URL(window.location.href);
        url.searchParams.delete('run_id');
        window.history.pushState({}, '', url.toString());
    }, [clearResults]);

    if (isLoading) {
        return (
            <div className="h-full w-full flex items-center justify-center text-text-primary">
                <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
            </div>
        );
    }

    if (error || !config) {
        return (
            <div className="h-full w-full flex items-center justify-center text-red-500">
                <p>{error || "Configuration error"}</p>
            </div>
        );
    }

    const hasTopPicks = topPicks.length > 0;

    return (
        <div className="h-full w-full relative flex flex-col overflow-hidden">
            {/* Top Controls Bar - Left side only */}
            <div className="absolute top-4 left-4 z-400 flex flex-col gap-2">
                {/* Row 1: Filters, Layers, Legend & Agent Tuner */}
                <div className="flex items-start gap-2">
                    <FilterPanel
                        filters={filters}
                        onFiltersChange={setFilters}
                        onApply={() => { }} // Filters now work via Intelligence Map
                    />
                    <LayersPanel
                        layers={layers}
                        onLayersChange={setLayers}
                    />
                    <MapLegend hasSearchLocation={!!searchLocation} />
                    <AgentRefinementHUD
                        activeRunId={activeRunId}
                        currentQuery={currentQuery || ''}
                        onRunSwitch={handleSelectRun}
                        isOpen={isAgentHUDOpen}
                        onToggle={() => setIsAgentHUDOpen(!isAgentHUDOpen)}
                    />
                </div>

                {/* Row 2: Run Selector & Stats */}
                <div className="flex items-center gap-2">
                    <MapRunSelector
                        history={history}
                        activeRunId={activeRunId}
                        isLoading={isLoadingRun}
                        onSelectRun={handleSelectRun}
                        onClearResults={handleClearResults}
                    />

                    {/* Stats Badge */}
                    <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-2xl px-4 py-2.5 flex items-center gap-4 shadow-xl shadow-black/40">
                        <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-lg bg-slate-700/50 flex items-center justify-center">
                                <Building2 className="w-3.5 h-3.5 text-slate-300" />
                            </div>
                            <div className="flex flex-col">
                                <span className="text-xs text-slate-400 leading-none">Visibili</span>
                                <span className="text-sm text-white font-bold leading-tight">{filteredMarkers.length}</span>
                            </div>
                        </div>
                        {activeRunId && !filters.showOnlyTopPicks && (
                            <>
                                <div className="w-px h-8 bg-white/10" />
                                <div className="flex items-center gap-2">
                                    <div className="w-6 h-6 rounded-lg bg-teal-500/20 flex items-center justify-center">
                                        <Building2 className="w-3.5 h-3.5 text-teal-400" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-xs text-slate-400 leading-none">Risultati</span>
                                        <span className="text-sm text-teal-400 font-bold leading-tight">
                                            {allMarkers.filter(m => m.tier === 2 || m.tier === 3).length}
                                        </span>
                                    </div>
                                </div>
                            </>
                        )}
                        {hasTopPicks && (
                            <>
                                <div className="w-px h-8 bg-white/10" />
                                <div className="flex items-center gap-2">
                                    <div className="w-6 h-6 rounded-lg bg-linear-to-br from-amber-400/30 to-orange-400/30 flex items-center justify-center">
                                        <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-xs text-slate-400 leading-none">Top AI</span>
                                        <span className="text-sm text-amber-400 font-bold leading-tight">{topPicks.length}</span>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </div>

            {/* Map Container */}
            <div className={`flex-1 relative rounded-xl overflow-hidden shadow-2xl border border-white/5 m-4 mt-1 ${hasTopPicks ? 'mb-36' : ''}`}>
                <Map
                    markers={filteredMarkers}
                    center={config.center}
                    zoom={config.zoom}
                    overlays={layers.showMunicipi ? overlays : undefined}
                    pois={pois}
                    zoneOMI={layers.showZoneOMI ? zoneOMIOverlay : null}
                    selectedBuildingIds={selectedBuildings.map(b => b.id)}
                    focusMarkerId={focusMarkerId}
                    hoveredMarkerId={hoveredMarkerId}
                    searchLocation={searchLocation}
                    onMarkerClick={handleMarkerClick}
                    onClusterClick={handleClusterClick}
                />
            </div>

            {/* Results Carousel - Bottom */}
            {hasTopPicks && (
                <div className="absolute bottom-0 left-0 right-0 bg-linear-to-t from-[#0a0d12] via-[#0a0d12]/95 to-transparent pt-6 pb-4 z-300">
                    <ResultsCarousel
                        topPicks={topPicks}
                        selectedId={carouselSelectedId}
                        hoveredId={hoveredMarkerId}
                        onCardClick={handleCarouselCardClick}
                        onCardHover={handleCarouselHover}
                        sidebarOpen={isSidebarOpen}
                    />
                </div>
            )}

            {/* Building Sidebar */}
            <BuildingSidebar
                isOpen={isSidebarOpen}
                onClose={() => setIsSidebarOpen(false)}
                selectedBuildings={selectedBuildings}
            />
        </div>
    );
};
