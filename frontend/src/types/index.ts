export interface RouteFareDetail {
  base_period_fare: number
  as_of_period_fare: number
  relative: number
  weight: number
}

export interface IndexResult {
  index_value: number
  base_period: string
  as_of_period: string
  methodology_version: string
  change_from_base_pct: number
  route_contributions: Record<string, number>
  airline_contributions: Record<string, number>
  route_fares: Record<string, RouteFareDetail>
  calculation_breakdown: string[]
  n_observations_used: number
  routes_missing_data: string[]
}

export interface IndexTrendPoint {
  period: string
  index_value: number | null
  n_observations_used: number
}

export interface IndexTrend {
  series: IndexTrendPoint[]
  methodology_version: string
}

export interface ForecastPoint {
  period: string
  forecast_value: number
  lower_80: number
  upper_80: number
  lower_95: number
  upper_95: number
  trend_direction: 'UPWARD' | 'DOWNWARD' | 'STABLE'
}

export interface IndexForecastResult {
  forecast_available: boolean
  historical_periods_used: number
  monthly_drift_rate: number
  projected_horizon_growth_pct: number
  forecast_points: ForecastPoint[]
  note?: string
}

export interface DashboardSummary {
  index: IndexResult
  n_routes_tracked: number
  n_airlines_tracked: number
  current_period: string
  base_period: string
}

export interface Route {
  id: number
  origin: string
  destination: string
  weight: number
  distance_tier: string | null
  active: boolean
}

export interface Airline {
  id: number
  name: string
  iata_code: string | null
  active: boolean
}

export interface FareObservation {
  id: number
  origin: string
  destination: string
  airline: string
  flight_number: string | null
  travel_date: string
  collection_timestamp: string
  booking_window_days: number | null
  total_fare: number | null
  availability_status: string
  source: string
  source_type: 'LIVE_SCRAPE' | 'PUBLIC_DATASET' | 'DEMO_SIMULATED' | string
  data_quality_status: 'VALID' | 'SUSPICIOUS' | 'INVALID' | 'UNAVAILABLE' | string
  quality_flags: string | null
}

export interface DataQualitySummary {
  total_rows: number
  valid: number
  suspicious: number
  invalid: number
  unavailable: number
  duplicates_removed: number
  outliers_iqr: number
  outliers_mad: number
  valid_pct: number
  issues_sample: string[]
}

export interface IngestionRunRow {
  id: number
  data_source_id: number
  status: 'RUNNING' | 'SUCCESS' | 'SOURCE_UNAVAILABLE' | 'FAILED' | string
  started_at: string
  completed_at: string | null
  rows_collected: number
  rows_valid: number
  error_message: string | null
}

export interface DataSourceItem {
  id: number
  name: string
  source_type: string
  active: boolean
  last_success_at: string | null
  last_failure_reason: string | null
}

export interface UserItem {
  id: number
  email: string
  role: 'ADMIN' | 'ANALYST' | 'VIEWER' | string
  is_active: boolean
}

export interface IndexConfigItem {
  id: number
  base_period: string
  methodology_version: string
  booking_window_weights: Record<string, number> | null
  include_suspicious: boolean
  is_active: boolean
  created_by: string | null
  created_at: string
  notes: string | null
}

export interface BacktestResult {
  start_period: string
  end_period: string
  reference_dataset: string
  reference_available: boolean
  mae: number | null
  rmse: number | null
  mape: number | null
  correlation: number | null
  points: Array<{ period: string; actual: number; reference: number }>
  note?: string
}

export interface AuditLogRow {
  id: number
  user_email: string | null
  action: string
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown> | null
  timestamp: string
}

export interface CpiPoint {
  period: string
  official_general_cpi: number
  augmented_general_cpi: number
  official_transport_cpi: number
  augmented_transport_cpi: number
  apix_value: number
  inflation_delta_bps: number
}

export interface CpiSimulationResponse {
  airfare_weight_pct: number
  transport_weight_pct: number
  points: CpiPoint[]
  mean_headline_delta_bps: number
  max_headline_delta_bps: number
  lag_reduction_days_est: number
  policy_summary: string
}

export interface FareAnomaly {
  route: string
  origin: string
  destination: string
  airline: string
  travel_date: string
  booking_window_days: number | null
  observed_fare: number
  route_median_fare: number
  deviation_pct: number
  anomaly_type: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  description: string
}
