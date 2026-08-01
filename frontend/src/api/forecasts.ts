import { request } from './http'
import type { ForecastResponse } from '../types'

export const forecastsApi = {
  forecast: (id: number, horizon = 30, method = 'auto') =>
    request<ForecastResponse>(
      `/forecasts/datasets/${id}?horizon=${horizon}&method=${method}`
    ),
}
