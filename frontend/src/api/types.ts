/**
 * Shared Type Definitions mirroring backend Pydantic models
 */

export interface AccessToken {
    access_token: string;
    token_type: string;
    expires_in: number;
}

export interface User {
    id: number;
    username: string;
    email?: string;
    created_at: string;
}

export interface LoginRequest {
    username: string;
    password: string; // Plain text
}

export interface RegisterRequest {
    username: string;
    password: string;
    email?: string;
}

// Map Types
export interface LatLng {
    lat: number;
    lng: number;
}

export interface ApiCoordinates {
    lat: number;
    lng?: number;
    lon?: number;
}

// Tier enum for Intelligence Map
export type MarkerTier = 1 | 2 | 3;

export interface MapMarkerLite {
    id: string;
    lat: number;
    lng: number;
    tier: number;
    price?: number;
    surface?: number;
    energy_class?: string;
    year?: string;
    type?: string;
    usage?: string;
    is_meta?: boolean;
}

export interface MapMarker {
    id: string;
    lat: number;
    lng: number;
    // Full data from dataset
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
    is_evaluated?: boolean;
    is_match?: boolean;
    is_meta_building?: boolean;
    // New fields
    meta_property?: string;
    annual_rent?: number;
    third_party_tenure_type?: string;
    start_date?: string;
    cadastral_units_count?: number;
    id_list?: string;
    sub_properties?: {
        id: string;
        surface_area?: number;
        property_type?: string;
    }[];
    // Extended property info
    property_type?: string;
    legal_nature?: string;
    cultural_constraint?: string;
    purpose?: string;
    omi_zone?: string;
    cadastral_sheet?: string;
    cadastral_parcel?: string;
    energy_scores?: {
        total?: number;
        class_score?: number;
        system_score?: number;
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
    // Italian aliases and fields
    meta_immobile?: boolean;
    canone_annuale?: number;
    tipo_detenzione_a_terzi?: string;
    data_decorrenza?: string;
    numero_immobili_per_catasto?: number;
    ape_scores?: Partial<EnergyScores>;
    poi_scores?: Partial<ProximityScores>;
    ape_files?: string[];
    // English aliases for BuildingDetail compatibility
    effective_date?: string;           // alias for data_decorrenza
    // Intelligence Map - AI Evaluation fields
    tier?: MarkerTier; // 1=Background, 2=Search Results, 3=Top Picks
    evaluation_text?: string;
    pros?: string[];
    cons?: string[];
    ranking_score?: number; // AI-computed score for Top Picks ordering
    location_score?: number;
    regulatory_score?: number;
    energy_score?: number;
    building_score?: number;
    proximity_score?: number;
    ranking_weight_location?: number;
    ranking_weight_regulatory?: number;
    ranking_weight_energy?: number;
    ranking_weight_building?: number;
    ranking_weight_proximity?: number;
    meta_building?: boolean;
}

export interface MapConfig {
    center: LatLng;
    zoom: number;
    style: string;
    attribution: string;
}

// Building Details Types
export interface EnergyScores {
    total?: number;
    class_score?: number;
    system_score?: number;
    plant_score?: number;
    envelope_score?: number;
    renewables_score?: number;
}

export interface ProximityScores {
    healthcare?: number;
    mobility?: number;
    greenery?: number;
    education?: number;
    commerce?: number;
    sport?: number;
}

export interface BuildingResponse {
    id: string;
    address?: string;
    city?: string;
    coordinates: ApiCoordinates;
    surface_area?: number;
    construction_year?: string;
    energy_class?: string;
    score?: number;
    rooms?: number;
    bathrooms?: number;
    floor?: string;
    price?: number;
    description?: string;
    is_evaluated: boolean;
    is_match: boolean;
    is_meta_building: boolean;
    meta_building?: boolean;
    // New fields
    meta_property?: string;
    annual_rent?: number;
    third_party_tenure_type?: string;
    start_date?: string;
    effective_date?: string;
    cadastral_units_count?: number;
    id_list?: string;
    energy_scores?: EnergyScores;
    proximity_scores?: ProximityScores;
    distance_km?: number;
    proximity_reference?: string;
    location_score?: number;
    regulatory_score?: number;
    energy_score?: number;
    building_score?: number;
    proximity_score?: number;
    ranking_weight_location?: number;
    ranking_weight_regulatory?: number;
    ranking_weight_energy?: number;
    ranking_weight_building?: number;
    ranking_weight_proximity?: number;
    // Extended fields
    energy_files?: string[];
    property_type?: string;
    legal_nature?: string;
    cultural_constraint?: string;
    purpose?: string;
    omi_zone?: string;
    cadastral_sheet?: string;
    cadastral_parcel?: string;
    sub_properties?: {
        id: string;
        surface_area?: number;
        property_type?: string;
    }[];
}

export interface BuildingsListResponse {
    buildings: BuildingResponse[];
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
}

export interface POI {
    id: number | string;
    lat: number;
    lon: number;
    name: string;
    category: string;
    icon: string;
    color: string;
    details?: {
        address?: string;
        city?: string;
        website?: string;
        phone?: string;
        opening_hours?: string;
        description?: string;
        operator?: string;
    };
}

export interface POIResponse {
    count: number;
    categories: string[];
    pois: POI[];
}

// =============================================================================
// Analysis Types (matches backend API)
// =============================================================================

export type AnalysisMode = 'agent';
export type DatasetKey = 'full' | 'meta' | 'ape';
export type AnalysisStatusType = 'pending' | 'processing' | 'completed' | 'failed';

export interface AnalysisRequest {
    query: string;
    dataset_key?: DatasetKey;
    map_limit?: number;
    llm_limit?: number;
    analysis_mode?: AnalysisMode;
}

export interface AnalysisStartResponse {
    run_id: string;
    status: AnalysisStatusType;
    message: string;
    created_at: string;
}

export interface LocationInfo {
    name: string;
    lat: number;
    lon: number;
}

export interface GeminiResponses {
    analysis_mode: string;
    dataset_key: string;
    location_extraction?: {
        places: Array<{ name: string; city?: string; lat?: number; lon?: number }>;
        response: string;
    };
    property_technical_extraction?: {
        typologies: string[];
        response: string;
    };

    sql_generation?: {
        sql_query: string;
        response: string;
    };
    evaluation?: {
        results: Array<{
            id: number | string;
            evaluation_text: string;
            score?: number;
            final_ranking_score?: number;
            pros?: string[];
            cons?: string[];
        }>;
    };
    broker_review?: string;
    [key: string]: unknown;
}

export interface AnalysisResults {
    run_id: string;
    status: AnalysisStatusType;
    query: string;
    created_at: string;
    completed_at?: string;
    buildings: BuildingResponse[];
    location: Array<[string, number, number]>; // [name, lat, lon]
    filters_applied?: {
        where_clause?: string;
    };
    gemini_responses?: GeminiResponses;
    broker_summary?: string;
    agent_trace?: AgentTraceItem[];
    html_log?: string;
}

export interface AgentTraceItem {
    agent_name: string;
    agent_mode: string;
    timestamp: string; // ISO
    execution_time_ms: number;
    input: unknown;
    output: unknown;
    output_structure?: unknown;
    notes?: string;
    batch_id?: number | null;
    retry_id?: number;
    use_case?: string;
    prompt_id?: string;
    run_number?: number;
    run_timestamp?: string;
}

/**
 * Structure of the prompt record sent to the LLM model.
 * - system: System instructions defining agent role and behavior
 * - user: User message template with replaced variables
 * - full_text: Complete concatenation (for debugging)
 */
export interface PromptRecord {
    system: string;
    user: string;
    full_text?: string;
}

export interface AgentStep {
    key: string;
    label?: string;
    prompt?: PromptRecord | null;
    response?: unknown;
    data?: Record<string, unknown> | null;
}

export interface AgentStepsResponse {
    run_id: string;
    steps: AgentStep[];
}

export interface AnalysisHistoryItem {
    run_id: string;
    query: string;
    status: AnalysisStatusType;
    created_at: string;
    completed_at?: string;
    buildings_count?: number;
    analysis_mode?: string;
}

// WebSocket Progress Types
export interface ProgressStep {
    label: string;
    state: 'done' | 'current' | 'pending';
    detail?: string;
}

export interface ProgressUpdate {
    type: 'progress';
    run_id?: string;
    progress: number;
    step: string;
    detail: string;
    steps_state?: ProgressStep[];
}
export interface ProgressComplete {
    type: 'complete';
    run_id: string;
    message?: string;
    results_url: string;
}

export interface ProgressError {
    type: 'error';
    message?: string;
}

export type WebSocketMessage = ProgressUpdate | ProgressComplete | ProgressError;

// Agent Feedback Types
export interface AgentFeedbackSubmit {
    run_id: string;
    agent_name?: string;  // null/undefined for global feedback
    rating: 1 | 2 | 3 | 4 | 5;
    comment?: string;
}

export interface BuildingFeedbackSubmit {
    run_id: string;
    building_id: string;
    rating: 1 | 2 | 3 | 4 | 5;
    comment?: string;
    helpful?: boolean;
}

export interface AgentFeedbackResponse {
    id: number;
    run_id: string;
    agent_name?: string;
    building_id?: string;
    rating: number;
    comment?: string;
    created_at: string;
    user_id?: number;
}
