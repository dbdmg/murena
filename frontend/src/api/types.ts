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

// Tier enum for Intelligence Map
export type MarkerTier = 1 | 2 | 3;

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
    meta_building?: boolean;
    // New fields
    meta_immobile?: boolean;
    canone_annuale?: number;
    tipo_detenzione_a_terzi?: string;
    data_decorrenza?: string;
    numero_immobili_per_catasto?: number;
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
    // Intelligence Map - AI Evaluation fields
    tier?: MarkerTier; // 1=Background, 2=Search Results, 3=Top Picks
    evaluation_text?: string;
    pros?: string[];
    cons?: string[];
    ranking_score?: number; // AI-computed score for Top Picks ordering
}

export interface MapConfig {
    center: LatLng;
    zoom: number;
    style: string;
    attribution: string;
}

// Building Details Types
export interface APEScores {
    total: number;
    class_score: number;
    system_score: number;
    envelope_score: number;
    renewables_score: number;
}

export interface POIScores {
    health?: number;
    mobility?: number;
    green?: number;
    education?: number;
    shopping?: number;
}

export interface BuildingResponse {
    id: string;
    address?: string;
    city?: string;
    coordinates: LatLng;
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
    meta_building: boolean;
    // New fields
    meta_immobile?: boolean;
    canone_annuale?: number;
    tipo_detenzione_a_terzi?: string;
    data_decorrenza?: string;
    numero_immobili_per_catasto?: number;
    id_list?: string;
    ape_scores?: APEScores;
    poi_scores?: POIScores;
    distance_km?: number;
    poi_reference?: string;
    // Extended fields
    ape_files?: string[];
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
    typology_extraction?: {
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
    html_log?: string;
}

/**
 * Struttura del record prompt inviato al modello LLM.
 * - system: Istruzioni di sistema che definiscono ruolo e comportamento dell'agente
 * - user: Template/messaggio dell'utente con le variabili sostituite
 * - full_text: Concatenazione completa (per debug)
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

export type WebSocketMessage = ProgressUpdate | ProgressComplete;
