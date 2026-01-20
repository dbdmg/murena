import { useState, useEffect, useCallback, useMemo } from 'react';
import type { MapMarker, MarkerTier, AnalysisHistoryItem } from '../api/types';
import { analysisApi } from '../api/endpoints/analysis';
import { mapApi } from '../api/endpoints/map';

const MAX_HISTORY = 10;

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
                const markers = await mapApi.getMarkers({ limit: markersLimit });
                // Assign tier 1 to all background markers
                const tier1Markers: MapMarker[] = markers.map(m => ({
                    ...m,
                    tier: 1 as MarkerTier,
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
        } catch (err) {
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
                evaluationResults.map((e: any) => [String(e.id), e])
            );

            // Convert buildings to markers with tier assignment
            const allAnalysisMarkers: MapMarker[] = results.buildings
                .filter((b: any) => b?.coordinates?.lat != null && b?.coordinates?.lon != null)
                .map((b: any) => {
                    const evalData = evaluationMap.get(String(b.id));
                    const isEvaluated = !!evalData;

                    return {
                        id: String(b.id),
                        lat: b.coordinates.lat,
                        lng: b.coordinates.lon,
                        address: b.address,
                        city: b.city,
                        surface_area: b.surface_area,
                        construction_year: b.construction_year,
                        energy_class: b.energy_class,
                        score: evalData?.score ?? b.score,
                        description: b.description,
                        is_evaluated: isEvaluated,
                        meta_building: b.meta_building,
                        // New metadata fields
                        meta_immobile: b.meta_immobile,
                        canone_annuale: b.canone_annuale,
                        tipo_detenzione_a_terzi: b.tipo_detenzione_a_terzi,
                        data_decorrenza: b.data_decorrenza,
                        numero_immobili_per_catasto: b.numero_immobili_per_catasto,
                        id_list: b.id_list,
                        // Scores and extended info
                        ape_scores: b.ape_scores,
                        poi_scores: b.poi_scores,
                        ape_files: b.ape_files,
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
                        ranking_score: evalData?.score,
                    } as MapMarker;
                });

            // Separate into Tier 2 (non-evaluated) and Tier 3 (evaluated)
            const tier3Candidates = allAnalysisMarkers
                .filter(m => m.is_evaluated && m.ranking_score != null)
                .sort((a, b) => (b.ranking_score ?? 0) - (a.ranking_score ?? 0))
                .slice(0, 25) // Max 25 top picks
                .map(m => ({ ...m, tier: 3 as MarkerTier }));

            const tier3Ids = new Set(tier3Candidates.map(m => m.id));

            const tier2Markers = allAnalysisMarkers
                .filter(m => !tier3Ids.has(m.id))
                .map(m => ({ ...m, tier: 2 as MarkerTier }));

            // Add to history
            addToHistory({
                run_id: runId,
                query: results.query,
                status: results.status,
                created_at: results.created_at,
                completed_at: results.completed_at,
                buildings_count: results.buildings.length,
            });

            setState(prev => ({
                ...prev,
                isLoading: false,
                activeRunId: runId,
                currentQuery: results.query || null,
                searchResults: tier2Markers,
                topPicks: tier3Candidates,
                searchLocation,
            }));
        } catch (err) {
            console.error('Failed to load analysis run:', err);
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
