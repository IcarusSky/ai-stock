import axios from 'axios'

const API_BASE = '/api'

// 默认超时：30s（普通查询）
// LLM 相关接口单独放宽：120s（模型推理耗时长）
const LLM_TIMEOUT = 120000

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

// 行情API
export const marketApi = {
  getQuote: (code: string) => api.get(`/market/quote/${code}`),
  getQuotes: (codes: string[]) => api.get(`/market/quotes?stock_codes=${codes.join(',')}`),
  getKline: (code: string, period = 'daily') => api.get(`/market/kline/${code}?period=${period}`),
  getSentiment: () => api.get('/market/sentiment'),
  getWatchlist: () => api.get('/market/watchlist'),
}

// 持仓API
export const portfolioApi = {
  getPositions: () => api.get('/portfolio/positions'),
  getCapitalCurve: (days = 30) => api.get(`/portfolio/capital_curve?days=${days}`),
  getAccount: () => api.get('/portfolio/account'),
  getTrades: () => api.get('/portfolio/trades'),
}

// 策略API
export const strategyApi = {
  list: () => api.get('/strategy/list'),
  register: (data: any) => api.post('/strategy/register', data),
  update: (id: string, data: any) => api.put(`/strategy/${id}`, data),
  delete: (id: string) => api.delete(`/strategy/${id}`),
  getSignal: (strategyId: string, stockCode: string) =>
    api.get(`/strategy/${strategyId}/signal?stock_code=${stockCode}`),
  evaluate: () => api.post('/strategy/evaluate', null, { timeout: LLM_TIMEOUT }),
  getDailyRecommend: () => api.get('/strategy/daily/recommend', { timeout: LLM_TIMEOUT }),
}

// 订单API
export const orderApi = {
  buy: (data: any) => api.post('/order/buy', data),
  sell: (data: any) => api.post('/order/sell', data),
  cancel: (orderId: string) => api.post('/order/cancel', { order_id: orderId }),
  getOrder: (orderId: string) => api.get(`/order/${orderId}`),
}

// 回测API
export const backtestApi = {
  run: (data: any) => api.post('/backtest/run', data, { timeout: LLM_TIMEOUT }),
  getResult: (taskId: string) => api.get(`/backtest/${taskId}/result`),
  getStatus: (taskId: string) => api.get(`/backtest/${taskId}/status`),
  compare: (strategyIds: string[], startDate: string, endDate: string) =>
    api.get(`/backtest/compare?strategy_ids=${strategyIds.join(',')}&start_date=${startDate}&end_date=${endDate}`, { timeout: LLM_TIMEOUT }),
  optimize: (strategyId: string, paramName: string) =>
    api.post('/backtest/optimize', { strategy_id: strategyId, param_name: paramName }, { timeout: LLM_TIMEOUT }),
}

// 新闻API
export const newsApi = {
  getRealtime: () => api.get('/news/realtime'),
  analyze: (newsId: string, stockCode?: string) =>
    api.get(`/news/analyze/${newsId}${stockCode ? `?stock_code=${stockCode}` : ''}`, { timeout: LLM_TIMEOUT }),
  analyzeBatch: (newsIds: string[], stockCode?: string) =>
    api.post(`/news/analyze/batch?stock_code=${stockCode || ''}`, newsIds, { timeout: LLM_TIMEOUT }),
  getSentimentReport: () => api.get('/news/market_sentiment', { timeout: LLM_TIMEOUT }),
  getStockNews: (stockCode: string) => api.get(`/news/stock_impact/${stockCode}`),
}

// LLM API
export const llmApi = {
  generateStrategy: (description: string) =>
    api.post('/llm/strategy/generate', { description }, { timeout: LLM_TIMEOUT }),
  validateStrategy: (strategy: any) => api.post('/llm/strategy/validate', strategy, { timeout: LLM_TIMEOUT }),
  previewStrategy: (description: string) =>
    api.post('/llm/strategy/preview', { description }, { timeout: LLM_TIMEOUT }),
}

// 飞书API
export const feishuApi = {
  sendMessage: (content: string) => api.post('/feishu/send_message', { content }),
  sendCard: (title: string, content: string) =>
    api.post('/feishu/send_card', { title, content }),
  setWebhook: (webhookUrl: string) => api.post('/feishu/set_webhook', { webhook_url: webhookUrl }),
  test: () => api.post('/feishu/test'),
  getLogs: () => api.get('/feishu/push_logs'),
}

// 数据源API（同花顺iFinD / 免费通道 / 问财选股）
export const dataSourceApi = {
  status: () => api.get('/datasource/status'),
  wencai: (query: string) => api.post('/datasource/wencai', { query }),
}

// 企业数据API（天眼查）
export const companyApi = {
  profile: (keyword: string) => api.get(`/company/${encodeURIComponent(keyword)}/profile`),
  risk: (keyword: string) => api.get(`/company/${encodeURIComponent(keyword)}/risk`),
  news: (keyword: string) => api.get(`/company/${encodeURIComponent(keyword)}/news`),
}

export default api
