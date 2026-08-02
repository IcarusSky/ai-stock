import { useState, useEffect } from 'react'
import { Card, Row, Col, List, Tag, Typography, Button, Space, Modal, Spin, Badge, Empty, Segmented } from 'antd'
import { ReadOutlined, ThunderboltOutlined, AlertOutlined, CaretUpOutlined, CaretDownOutlined } from '@ant-design/icons'
import { newsApi } from '../services/api'

const { Title, Text, Paragraph } = Typography

interface NewsItem {
  id: string
  title: string
  content?: string
  source: string
  published_at: string
  sentiment: string
  sentiment_score: number
  is_buy_signal: boolean
  related_stocks: string[]
  impact_scope: string
}

interface SentimentReport {
  date: string
  overall_sentiment: number
  sentiment_trend: string
  bullish_news_count: number
  bearish_news_count: number
  neutral_news_count: number
  hot_sectors: any[]
  hot_stocks: any[]
  risk_alerts: string[]
  summary: string
}

export default function News() {
  const [news, setNews] = useState<NewsItem[]>([])
  const [report, setReport] = useState<SentimentReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null)
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const [filterType, setFilterType] = useState<string>('all')
  const [wsConnected, setWsConnected] = useState(false)

  const loadNews = async () => {
    setLoading(true)
    try {
      const res = await newsApi.getRealtime()
      setNews(res.data)
    } catch (error) {
      console.error('加载新闻失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadReport = async () => {
    try {
      const res = await newsApi.getSentimentReport()
      setReport(res.data)
    } catch (error) {
      console.error('加载情绪报告失败:', error)
    }
  }

  useEffect(() => {
    loadNews()
    loadReport()
  }, [])

  useEffect(() => {
    const wsBaseUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
    const wsUrl = `${wsBaseUrl}/api/news/ws/realtime`
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        setWsConnected(true)
        console.log('新闻 WebSocket 已连接')
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'pong') return
          if (msg.type === 'news') {
            const item: NewsItem = msg.data
            setNews((prev) => {
              const filtered = prev.filter((n) => n.id !== item.id)
              const next = [item, ...filtered]
              return next.slice(0, 200)
            })
          }
        } catch (err) {
          console.error('解析 WebSocket 消息失败:', err)
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        console.log('新闻 WebSocket 已断开，3秒后重连...')
        reconnectTimer = setTimeout(connect, 3000)
      }

      ws.onerror = (err) => {
        console.error('新闻 WebSocket 错误:', err)
      }
    }

    connect()

    return () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
      }
      if (ws) {
        ws.onclose = null
        ws.close()
      }
    }
  }, [])

  const analyzeNews = async (newsItem: NewsItem) => {
    setSelectedNews(newsItem)
    setAnalyzingId(newsItem.id)
    setAnalysisResult(null)

    try {
      const res = await newsApi.analyze(newsItem.id)
      setAnalysisResult(res.data)
    } catch (error) {
      console.error('分析失败:', error)
    } finally {
      setAnalyzingId(null)
    }
  }

  const getSentimentTag = (sentiment: string, score: number) => {
    if (sentiment === 'BULLISH') {
      return <Tag icon={<CaretUpOutlined />} color="green">利好 {(score * 100).toFixed(0)}%</Tag>
    } else if (sentiment === 'BEARISH') {
      return <Tag icon={<CaretDownOutlined />} color="red">利空 {(Math.abs(score) * 100).toFixed(0)}%</Tag>
    }
    return <Tag>中性</Tag>
  }

  const filteredNews = news.filter(n => {
    if (filterType === 'all') return true
    if (filterType === 'bullish') return n.sentiment === 'BULLISH'
    if (filterType === 'bearish') return n.sentiment === 'BEARISH'
    if (filterType === 'buy_signal') return n.is_buy_signal
    return true
  })

  return (
    <div>
      <Title level={4}>📰 新闻分析</Title>

      {/* 市场情绪总览 */}
      {report && (
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={4}>
              <div style={{ textAlign: 'center' }}>
                <Text type="secondary">整体情绪</Text>
                <div style={{ fontSize: 32, fontWeight: 'bold', color: report.overall_sentiment > 0 ? '#52c41a' : report.overall_sentiment < 0 ? '#f5222d' : '#999' }}>
                  {report.overall_sentiment > 0 ? '+' : ''}{(report.overall_sentiment * 100).toFixed(0)}%
                </div>
              </div>
            </Col>
            <Col span={4}>
              <div style={{ textAlign: 'center' }}>
                <Text type="secondary">情绪趋势</Text>
                <div style={{ fontSize: 18, marginTop: 8 }}>
                  <Tag color={report.sentiment_trend === 'IMPROVING' ? 'green' : report.sentiment_trend === 'DETERIORATING' ? 'red' : 'default'}>
                    {report.sentiment_trend === 'IMPROVING' ? '↗ 改善' : report.sentiment_trend === 'DETERIORATING' ? '↘ 恶化' : '→ 稳定'}
                  </Tag>
                </div>
              </div>
            </Col>
            <Col span={4}>
              <div style={{ textAlign: 'center' }}>
                <Text type="secondary">利好/利空/中性</Text>
                <div style={{ fontSize: 18, marginTop: 8 }}>
                  <Tag color="green">{report.bullish_news_count}</Tag>
                  <Tag color="red">{report.bearish_news_count}</Tag>
                  <Tag>{report.neutral_news_count}</Tag>
                </div>
              </div>
            </Col>
            <Col span={6}>
              <Text type="secondary">热点板块：</Text>
              <div style={{ marginTop: 4 }}>
                {report.hot_sectors.map((s, i) => (
                  <Tag key={i} color={s.sentiment === 'BULLISH' ? 'green' : 'red'}>{s.name}</Tag>
                ))}
              </div>
            </Col>
            <Col span={6}>
              <Text type="secondary">热点股票：</Text>
              <div style={{ marginTop: 4 }}>
                {report.hot_stocks.map((s: any, i: number) => (
                  <Tag key={i} color={s.sentiment === 'BULLISH' ? 'blue' : 'orange'}>{s.name}</Tag>
                ))}
              </div>
            </Col>
          </Row>
          {report.risk_alerts && report.risk_alerts.length > 0 && (
            <div style={{ marginTop: 12 }}>
              {report.risk_alerts.map((alert, i) => (
                <Tag key={i} icon={<AlertOutlined />} color="warning">{alert}</Tag>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* 新闻列表 */}
      <Card
        title={
          <Space>
            实时新闻
            <Badge
              status={wsConnected ? 'success' : 'default'}
              text={<Text type="secondary">{wsConnected ? '实时连接' : '已断开'}</Text>}
            />
          </Space>
        }
        extra={
          <Space>
            <Segmented
              options={[
                { label: '全部', value: 'all' },
                { label: '利好', value: 'bullish' },
                { label: '利空', value: 'bearish' },
                { label: '买点信号', value: 'buy_signal' },
              ]}
              value={filterType}
              onChange={(v) => setFilterType(v as string)}
            />
            <Button icon={<ReadOutlined />} onClick={loadNews}>刷新</Button>
          </Space>
        }
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div>
        ) : (
          <List
            dataSource={filteredNews}
            renderItem={(item) => (
              <List.Item
                key={item.id}
                extra={
                  <Space>
                    {item.is_buy_signal && <Tag icon={<ThunderboltOutlined />} color="gold">买点信号</Tag>}
                    <Button size="small" onClick={() => analyzeNews(item)}>AI分析</Button>
                  </Space>
                }
              >
                <List.Item.Meta
                  title={
                    <Space>
                      {item.title}
                      {getSentimentTag(item.sentiment, item.sentiment_score)}
                    </Space>
                  }
                  description={
                    <Space>
                      <Text type="secondary">{item.source}</Text>
                      <Text type="secondary">{new Date(item.published_at).toLocaleString()}</Text>
                      {item.related_stocks?.map((code, i) => (
                        <Tag key={i}>{code}</Tag>
                      ))}
                      <Tag>{item.impact_scope === 'MARKET' ? '大盘' : item.impact_scope === 'SECTOR' ? '板块' : '个股'}</Tag>
                    </Space>
                  }
                />
              </List.Item>
            )}
            locale={{ emptyText: <Empty description="暂无新闻" /> }}
          />
        )}
      </Card>

      {/* AI分析弹窗 */}
      <Modal
        title="🤖 AI新闻分析"
        open={!!selectedNews}
        onCancel={() => { setSelectedNews(null); setAnalysisResult(null) }}
        footer={null}
        width={600}
      >
        {selectedNews && (
          <div>
            <Title level={5}>{selectedNews.title}</Title>
            <Space style={{ marginBottom: 16 }}>
              <Text type="secondary">{selectedNews.source}</Text>
              <Text type="secondary">{new Date(selectedNews.published_at).toLocaleString()}</Text>
            </Space>

            {analyzingId === selectedNews.id ? (
              <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div>
            ) : analysisResult ? (
              <div style={{ background: '#f5f5f5', padding: 16, borderRadius: 8 }}>
                <Row gutter={16} style={{ marginBottom: 12 }}>
                  <Col span={8}>
                    <Text type="secondary">情绪判断：</Text>
                    {getSentimentTag(analysisResult.sentiment, analysisResult.sentiment_score)}
                  </Col>
                  <Col span={8}>
                    <Text type="secondary">置信度：</Text>
                    <Text strong>{(analysisResult.confidence * 100).toFixed(0)}%</Text>
                  </Col>
                  <Col span={8}>
                    <Text type="secondary">建议：</Text>
                    <Tag color={
                      analysisResult.recommendation === 'BUY' ? 'green' :
                      analysisResult.recommendation === 'SELL' ? 'red' :
                      analysisResult.recommendation === 'WATCH' ? 'orange' : 'default'
                    }>
                      {analysisResult.recommendation === 'BUY' ? '买入' :
                       analysisResult.recommendation === 'SELL' ? '卖出' :
                       analysisResult.recommendation === 'WATCH' ? '观望' : '持有'}
                    </Tag>
                  </Col>
                </Row>

                {analysisResult.is_buy_signal && (
                  <div style={{ background: '#f6ffed', padding: 12, borderRadius: 4, border: '1px solid #b7eb8f', marginBottom: 12 }}>
                    <Text type="success"><ThunderboltOutlined /> 构成买点：{analysisResult.buy_signal_reason}</Text>
                  </div>
                )}

                {analysisResult.is_sell_signal && (
                  <div style={{ background: '#fff2f0', padding: 12, borderRadius: 4, border: '1px solid #ffccc7', marginBottom: 12 }}>
                    <Text type="danger"><AlertOutlined /> 构成卖点：{analysisResult.sell_signal_reason}</Text>
                  </div>
                )}

                <Paragraph><Text strong>影响分析：</Text>{analysisResult.impact_analysis}</Paragraph>

                {analysisResult.related_stocks?.length > 0 && (
                  <div>
                    <Text strong>相关股票：</Text>
                    <Space>
                      {analysisResult.related_stocks.map((code: string, i: number) => (
                        <Tag key={i}>{code}</Tag>
                      ))}
                    </Space>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}
      </Modal>
    </div>
  )
}
