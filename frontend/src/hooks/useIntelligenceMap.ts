import { useState, useEffect, useCallback, useMemo } from 'react';
import type { MapMarker, MarkerTier, AnalysisHistoryItem } from '../api/types';
import { analysisApi } from '../api/endpoints/analysis';
import { mapApi } from '../api/endpoints/map';

const MAX_HISTORY = 50;

export interface IntelligenceMapState {
    backgroundMarkers: MapMarker[]; // Tier 1 - gray
    searchResults: MapMarker[];      // Tier 2 - cyan
    topPicks: MapMarker[];           // Tier 3 - gold (max 25)
    searchLocation: { name: string; lat: number; lng: number } | null; // Red location marker
    activeRunId: string | null;
    currentQuery: string | null;     // Query of the active run
    isLoading: boolean;
    history: AnalysisHistoryItem[];
}

export interface UseIntelligenceMapReturn extends IntelligenceMapState {
    // All markers merged with proper tiers
    allMarkers: MapMarker[];
    // Load a specific run
    loadRun: (runId: string) => Promise<void>;
    // Clear current analysis results (back to background only)
    clearResults: () => void;
    // Refresh history from localStorage
    refreshHistory: () => void;
    // Add a run to history
    addToHistory: (item: AnalysisHistoryItem) => void;
    // Get marker by ID
    getMarkerById: (id: string) => MapMarker | undefined;
}

/**
 * Hook to manage the three-tier Intelligence Map system:
 * - Tier 1 (Background): Gray markers from settings limit
 * - Tier 2 (Search Results): Cyan markers from analysis
 * - Tier 3 (Top Picks): Gold markers with AI evaluation (max 25)
 */
export function useIntelligenceMap(
    markersLimit: number = 1000
): UseIntelligenceMapReturn {
    const [state, setState] = useState<IntelligenceMapState>({
        backgroundMarkers: [],
        searchResults: [],
        topPicks: [],
        searchLocation: null,
        activeRunId: null,
        currentQuery: null,
        isLoading: false,
        history: [],
    });

    // Load history from backend API on mount
    useEffect(() => {
        // Clean up old localStorage cache (migrated to API-based history)
        localStorage.removeItem('intelligence_map_history');

        const loadHistory = async () => {
            try {
                const history = await analysisApi.getHistory(MAX_HISTORY, 0);
                // Filter to only completed runs
                const completedHistory = history.filter(h => h.status === 'completed');
                setState(prev => ({ ...prev, history: completedHistory }));
            } catch (err) {
                console.warn('Failed to load history from API:', err);
            }
        };
        loadHistory();
    }, []);

    // Load background markers on mount
    useEffect(() => {
        const loadBackground = async () => {
            try {
                // Use new lightweight endpoint
                const liteMarkers = await mapApi.getMarkersLite({ limit: markersLimit });

                // Map to MapMarker type (filling required fields for TS, though optional in interface)
                const tier1Markers: MapMarker[] = liteMarkers.map(m => ({
                    id: m.id,
                    lat: m.lat,
                    lng: m.lng,
                    tier: 1 as MarkerTier,
                    // Map filter fields
                    price: m.price,
                    surface_area: m.surface,
                    energy_class: m.energy_class,
                    construction_year: m.year,
                    property_type: m.type,
                    description: m.usage,
                    meta_immobile: m.is_meta
                }));

                setState(prev => ({ ...prev, backgroundMarkers: tier1Markers }));
            } catch (err) {
                console.error('Failed to load background markers:', err);
            }
        };
        loadBackground();
    }, [markersLimit]);

    // Refresh history from backend API
    const refreshHistory = useCallback(async () => {
        try {
            const history = await analysisApi.getHistory(MAX_HISTORY, 0);
            const completedHistory = history.filter(h => h.status === 'completed');
            setState(prev => ({ ...prev, history: completedHistory }));
        } catch (err) {
            console.warn('Failed to refresh history from API:', err);
        }
    }, []);

    // Add a run to history (just refresh from API to stay in sync)
    const addToHistory = useCallback(async (item: AnalysisHistoryItem) => {
        // Instead of managing local state, just refresh from API
        // This ensures we stay in sync with the database
        try {
            const history = await analysisApi.getHistory(MAX_HISTORY, 0);
            const completedHistory = history.filter(h => h.status === 'completed');
            setState(prev => ({ ...prev, history: completedHistory }));
        } catch {
            // Fallback: add locally if API fails
            setState(prev => {
                const filtered = prev.history.filter(h => h.run_id !== item.run_id);
                const updated = [item, ...filtered].slice(0, MAX_HISTORY);
                return { ...prev, history: updated };
            });
        }
    }, []);

    // Load a specific analysis run
    const loadRun = useCallback(async (runId: string) => {
        setState(prev => ({ ...prev, isLoading: true }));

        try {
            const results = await analysisApi.getResults(runId);

            // Extract search location if available
            let searchLocation: { name: string; lat: number; lng: number } | null = null;
            if (results.location && results.location.length > 0) {
                const [name, lat, lng] = results.location[0];
                searchLocation = { name, lat, lng };
            }

            if (!results.buildings || results.buildings.length === 0) {
                setState(prev => ({
                    ...prev,
                    isLoading: false,
                    activeRunId: runId,
                    searchResults: [],
                    topPicks: [],
                    searchLocation,
                }));
                return;
            }

            // Get evaluation data if available
            const evaluationResults = results.gemini_responses?.evaluation?.results || [];
            const evaluationMap = new Map(
                evaluationResults.map(e => [String(e.id), e])
            );

            // Convert buildings to markers with tier assignment
            const allAnalysisMarkers: MapMarker[] = results.buildings
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                .filter(b => (b?.coordinates?.lat != null && b?.coordinates?.lng != null) || ((b?.coordinates as any)?.lon != null))
                .map(b => {
                    const evalData = evaluationMap.get(String(b.id));
                    // Fix: Respect backend is_evaluated flag if evalData is missing
                    const isEvaluated = !!evalData || b.is_evaluated;

                    return {
                        id: String(b.id),
                        lat: b.coordinates.lat,
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        lng: b.coordinates.lng ?? (b.coordinates as any).lon,
                        address: b.address,
                        city: b.city,
                        surface_area: b.surface_area,
                        construction_year: b.construction_year,
                        energy_class: b.energy_class,
                        score: evalData?.score ?? b.score,
                        description: b.description,
                        is_evaluated: isEvaluated,
                        is_match: b.is_match,
                        meta_building: b.meta_building,
                        // New metadata fields — Italian aliases
                        meta_immobile: b.meta_building,
                        canone_annuale: b.annual_rent,
                        tipo_detenzione_a_terzi: b.third_party_tenure_type,
                        data_decorrenza: b.effective_date,
                        numero_immobili_per_catasto: b.cadastral_units_count,
                        // English aliases for BuildingDetail compatibility
                        annual_rent: b.annual_rent,
                        third_party_tenure_type: b.third_party_tenure_type,
                        effective_date: b.effective_date,
                        cadastral_units_count: b.cadastral_units_count,
                        id_list: b.id_list,

                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        sub_properties: 'sub_properties' in b ? (b as any).sub_properties : undefined,
                        // Energy & proximity scores — mapped with the same names that BuildingDetail expects
                        energy_scores: b.energy_scores,
                        proximity_scores: b.proximity_scores,
                        // Keep legacy aliases for any code that still reads ape_scores/poi_scores
                        ape_scores: b.energy_scores,
                        poi_scores: b.proximity_scores,
                        // Energy files — use both field names for compatibility
                        energy_files: b.energy_files,
                        ape_files: b.energy_files,
                        property_type: b.property_type,
                        legal_nature: b.legal_nature,
                        cultural_constraint: b.cultural_constraint,
                        purpose: b.purpose,
                        omi_zone: b.omi_zone,
                        cadastral_sheet: b.cadastral_sheet,
                        cadastral_parcel: b.cadastral_parcel,
                        // AI Evaluation fields
                        evaluation_text: evalData?.evaluation_text,
                        pros: evalData?.pros,
                        cons: evalData?.cons,
                        // final_ranking_score is the real backend field; fallback to score for older runs
                        ranking_score: Math.round(
                            (evalData?.final_ranking_score ?? evalData?.score ?? b.score) ?? 0
                        ),
                        location_score: b.location_score,
                        regulatory_score: b.regulatory_score,
                        energy_score: b.energy_score,
                        building_score: b.building_score,
                        proximity_score: b.proximity_score,
                        ranking_weight_location: b.ranking_weight_location,
                        ranking_weight_regulatory: b.ranking_weight_regulatory,
                        ranking_weight_energy: b.ranking_weight_energy,
                        ranking_weight_building: b.ranking_weight_building,
                        ranking_weight_proximity: b.ranking_weight_proximity,
                    } as MapMarker;
                });

            // Separate into Tier 2 (non-evaluated matches) and Tier 3 (evaluated matches)
            const tier3Candidates = allAnalysisMarkers
                .filter(m => m.is_match && m.is_evaluated && m.ranking_score != null)
                .sort((a, b) => (b.ranking_score ?? 0) - (a.ranking_score ?? 0))
                .slice(0, 25) // Max 25 top picks
                .map(m => ({ ...m, tier: 3 as MarkerTier }));

            const tier3Ids = new Set(tier3Candidates.map(m => m.id));

            const tier2Markers = allAnalysisMarkers
                .filter(m => m.is_match && !tier3Ids.has(m.id))
                .map(m => ({ ...m, tier: 2 as MarkerTier }));

            // Tier 1 markers from analysis (rich data for non-matches)
            const tier1RichMarkers = allAnalysisMarkers
                .filter(m => !m.is_match)
                .map(m => ({ ...m, tier: 1 as MarkerTier }));

            // Add to history
            addToHistory({
                run_id: runId,
                query: results.query,
                status: results.status,
                created_at: results.created_at,
                completed_at: results.completed_at,
                buildings_count: results.buildings.filter(b => b.is_match).length,
            });

            setState(prev => ({
                ...prev,
                isLoading: false,
                activeRunId: runId,
                currentQuery: results.query || null,
                searchResults: tier2Markers,
                topPicks: tier3Candidates,
                backgroundMarkers: [
                    ...prev.backgroundMarkers.filter(m => !tier3Ids.has(m.id) && !tier2Markers.some(s => s.id === m.id) && !tier1RichMarkers.some(r => r.id === m.id)),
                    ...tier1RichMarkers
                ],
                searchLocation,
            }));
        } catch (err) {
            console.error('Failed to load analysis run:', err);
            // Log full error for debugging
            if (err instanceof Error) {
                console.error('Error details:', err.message, err.stack);
            }
            setState(prev => ({ ...prev, isLoading: false }));
        }
    }, [addToHistory]);

    // Clear current results
    const clearResults = useCallback(() => {
        setState(prev => ({
            ...prev,
            activeRunId: null,
            currentQuery: null,
            searchResults: [],
            topPicks: [],
            searchLocation: null,
        }));
    }, []);

    // Merge all markers with proper tier priority
    // Tier 3 > Tier 2 > Tier 1 (higher tier markers override lower tier for same ID)
    const allMarkers = useMemo(() => {
        const markerMap = new Map<string, MapMarker>();

        // Add tier 1 first (will be overwritten by higher tiers)
        state.backgroundMarkers.forEach(m => markerMap.set(m.id, m));

        // Add tier 2 (overwrites tier 1)
        state.searchResults.forEach(m => markerMap.set(m.id, m));

        // Add tier 3 (overwrites tier 2 and tier 1)
        state.topPicks.forEach(m => markerMap.set(m.id, m));

        return Array.from(markerMap.values());
    }, [state.backgroundMarkers, state.searchResults, state.topPicks]);

    // Get marker by ID
    const getMarkerById = useCallback((id: string) => {
        return allMarkers.find(m => m.id === id);
    }, [allMarkers]);

    return {
        ...state,
        allMarkers,
        loadRun,
        clearResults,
        refreshHistory,
        addToHistory,
        getMarkerById,
    };
}
