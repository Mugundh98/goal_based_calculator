import { api } from './client'

// Mirrors backend/app/schemas/ml.py

export interface ModelInfo {
  name: string
  version: number
  algorithm: string
  trained_at: string
  data_start: string
  data_end: string
}

export interface RankingMetrics {
  rows: number
  rank_ic: number
  top_pick_hit_rate: number
  top_pick_median_excess: number
  accuracy?: number
  macro_f1?: number
  log_loss?: number
  top_precision?: number
}

export interface ModelCard extends ModelInfo {
  // Shape depends on the model (see services/ml.py _summary).
  summary: {
    walk_forward?: Record<'model' | 'momentum' | 'random', RankingMetrics>
    leaky_random_split?: RankingMetrics
    importance?: { feature: string; mean_abs_shap: number }[]
    rows?: number
    funds?: number
    k?: number
    silhouette?: number
    k_scores?: { k: number; silhouette: number; inertia: number; gmm_bic: number }[]
    best_bic_k?: number
    gmm_agreement_ari?: number
    asset_class_ari?: number
    mae_12m_ahead?: Record<string, number>
  }
}

export interface Factor {
  feature: string
  label: string
  value: number | null
  contribution: number // SHAP, log-odds of "top quartile"
}

export interface RankedFund {
  fund_id: number
  name: string
  amc: string
  category: string
  predicted_quartile: number
  prob_top: number
  probabilities: number[]
  expected_quartile: number
  peer_rank: number
  peer_size: number
  factors: Factor[]
}

export interface Rankings {
  model: ModelInfo
  as_of: string
  peer_groups: { id: string; label: string; funds: number }[]
  peer_group: string | null
  funds: RankedFund[]
}

export interface ClusterProfile {
  cluster: number
  name: string
  funds: number
  median: Record<string, number>
  asset_classes: Record<string, number>
  top_peer_groups: { peer_group: string; funds: number }[]
}

export interface ClusterPoint {
  fund_id: number
  name: string
  category: string
  asset_class: string
  cluster: number
  volatility: number // %
  return_3y: number // %
}

export interface Clusters {
  model: ModelInfo
  as_of: string
  k: number
  silhouette: number
  asset_class_ari: number
  clusters: ClusterProfile[]
  points: ClusterPoint[]
}

export interface FundInsight {
  prediction: RankedFund | null
  peer_group: string | null
  peer_group_label: string | null
  cluster: number | null
  cluster_name: string | null
  as_of: string | null
}

export interface InflationForecast {
  model: ModelInfo
  history: { month: string; yoy: number }[]
  forecast: { month: string; p10: number; p50: number; p90: number }[]
  mae_12m_ahead: Record<string, number>
}

export async function getModelCards(): Promise<ModelCard[]> {
  const { data } = await api.get<ModelCard[]>('/api/ml/models')
  return data
}

export async function getRankings(peerGroup: string | null): Promise<Rankings> {
  const { data } = await api.get<Rankings>('/api/ml/rankings', { params: peerGroup ? { peer_group: peerGroup } : {} })
  return data
}

export async function getClusters(): Promise<Clusters> {
  const { data } = await api.get<Clusters>('/api/ml/clusters')
  return data
}

export async function getFundInsight(fundId: number): Promise<FundInsight> {
  const { data } = await api.get<FundInsight>(`/api/ml/funds/${fundId}`)
  return data
}

export async function getInflationForecast(): Promise<InflationForecast> {
  const { data } = await api.get<InflationForecast>('/api/ml/inflation')
  return data
}
