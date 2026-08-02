import { useEffect, useState } from 'react'
import {
  Card, Row, Col, Table, Tag, Space, Button, Tabs, Statistic, Badge,
  Typography, Spin, Segmented, message
} from 'antd'
import {
  AlertOutlined, FundOutlined, RiseOutlined, BarChartOutlined,
  FireOutlined, CheckCircleOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { monitorApi, moneyflowApi, lhbApi, patternsApi } from '../services/api'
import dayjs from 'dayjs'

const { Title } = Typography

interface Signal {
  id: string
  code: string
  name: string
  signal_type: string
  message: string
  price: number
  created_at: string
  is_read: boolean
}

export default function MarketMonitor() {
  const [activeTab, setActiveTab] = useState('signals')
  const [loading, setLoading] = useState(false)

  // 信号
  const [signals, setSignals] = useState<Signal[]>([])
  const [unreadCount, setUnreadCount] = useState(0)

  // 资金流
  const [flowPeriod, setFlowPeriod] = useState('today')
  const [flowDirection, setFlowDirection] = useState('inflow')
  const [flowRank, setFlowRank] = useState<any[]>([])
  const [sectorFlow, setSectorFlow] = useState<any[]>([])
  const [flowOverview, setFlowOverview] = useState<any>(null)

  // 龙虎榜
  const [lhbDirection, setLhbDirection] = useState('all')
  const [lhbList, setLhbList] = useState<any[]>([])

  // 形态
  const [patternStats, setPatternStats] = useState<any[]>([])
  const [scanning, setScanning] = useState(false)

  const loadSignals = async () => {
    try {
      const [res, countRes] = await Promise.all([
        monitorApi.getSignals({ limit: 50 }),
        monitorApi.unreadCount()
      ])
      setSignals(res.data)
      setUnreadCount(countRes.data.count)
    } catch (error) {
      console.error('加载信号失败:', error)
    }
  }

  const markRead = async (id: string) => {
    try {
      await monitorApi.markRead(id)
      loadSignals()
    } catch (error) {
      message.error('标记已读失败')
    }
  }

  const markAllRead = async () => {
    try {
      await monitorApi.markAllRead()
      loadSignals()
    } catch (error) {
      message.error('标记已读失败')
    }
  }

  const loadMoneyFlow = async () => {
    setLoading(true)
    try {
      const [rankRes, sectorRes, overviewRes] = await Promise.all([
        moneyflowApi.rank({ period: flowPeriod, direction: flowDirection, limit: 20 }),
        moneyflowApi.sector({ sector_type: 'concept', limit: 20 }),
        moneyflowApi.overview()
      ])
      setFlowRank(rankRes.data.items || [])
      setSectorFlow(sectorRes.data.items || [])
      setFlowOverview(overviewRes.data)
    } catch (error) {
      console.error('加载资金流失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadLHB = async () => {
    setLoading(true)
    try {
      const res = await lhbApi.today({ direction: lhbDirection, limit: 50 })
      setLhbList(res.data.items || [])
    } catch (error) {
      console.error('加载龙虎榜失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadPatterns = async () => {
    setLoading(true)
    try {
      const res = await patternsApi.stats({ limit: 200 })
      setPatternStats(res.data.items || [])
    } catch (error) {
      console.error('加载形态统计失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const scanPatterns = async () => {
    setScanning(true)
    try {
      await patternsApi.scan({ patterns: ['ma5_above_ma10', 'price_above_ma20', 'volume_surge', 'golden_cross'], market: 'all', limit: 50 })
      message.success('形态扫描已触发')
    } catch (error) {
      message.error('形态扫描失败')
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => {
    loadSignals()
  }, [])

  useEffect(() => {
    if (activeTab === 'moneyflow') loadMoneyFlow()
    if (activeTab === 'lhb') loadLHB()
    if (activeTab === 'patterns') loadPatterns()
  }, [activeTab, flowPeriod, flowDirection, lhbDirection])

  const signalColumns: ColumnsType<Signal> = [
    {
      title: '状态',
      dataIndex: 'is_read',
      width: 80,
      render: (is_read) => (
        is_read ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> : <Badge status="error" />
      )
    },
    { title: '股票', dataIndex: 'name', render: (name, r) => `${name}(${r.code})` },
    {
      title: '类型',
      dataIndex: 'signal_type',
      render: (type) => {
        const color = type === 'buy' ? 'green' : type === 'sell' ? 'red' : 'orange'
        const label = type === 'buy' ? '买入' : type === 'sell' ? '卖出' : '预警'
        return <Tag color={color}>{label}</Tag>
      }
    },
    { title: '消息', dataIndex: 'message', ellipsis: true },
    { title: '价格', dataIndex: 'price', render: (v) => v?.toFixed(2) },
    { title: '时间', dataIndex: 'created_at', render: (v) => dayjs(v).format('MM-DD HH:mm') },
    {
      title: '操作',
      render: (_, r) => (
        !r.is_read ? (
          <Button size="small" onClick={() => markRead(r.id)}>标记已读</Button>
        ) : null
      )
    }
  ]

  const flowColumns = [
    { title: '排名', dataIndex: 'rank', width: 60 },
    { title: '股票', dataIndex: 'name', render: (name: string, r: any) => `${name}(${r.code})` },
    { title: '现价', dataIndex: 'price', render: (v: number) => v?.toFixed(2) },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      render: (v: number) => <Tag color={v >= 0 ? 'red' : 'green'}>{v >= 0 ? '+' : ''}{v?.toFixed(2)}%</Tag>
    },
    {
      title: '主力净流入',
      dataIndex: 'main_net_inflow',
      render: (v: number) => `${(v / 10000).toFixed(0)}万`
    },
    {
      title: '净流入占比',
      dataIndex: 'main_inflow_rate',
      render: (v: number) => `${v?.toFixed(2)}%`
    }
  ]

  const sectorFlowColumns = [
    { title: '板块', dataIndex: 'name' },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      render: (v: number) => <Tag color={v >= 0 ? 'red' : 'green'}>{v >= 0 ? '+' : ''}{v?.toFixed(2)}%</Tag>
    },
    {
      title: '主力净流入',
      dataIndex: 'main_net_inflow',
      render: (v: number) => `${(v / 10000).toFixed(0)}万`
    }
  ]

  const lhbColumns = [
    { title: '股票', dataIndex: 'name', render: (name: string, r: any) => `${name}(${r.code})` },
    { title: '收盘价', dataIndex: 'close_price', render: (v: number) => v?.toFixed(2) },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      render: (v: number) => <Tag color={v >= 0 ? 'red' : 'green'}>{v >= 0 ? '+' : ''}{v?.toFixed(2)}%</Tag>
    },
    {
      title: '主力净买入',
      dataIndex: 'main_net_buy',
      render: (v: number) => `${(v / 10000).toFixed(0)}万`
    },
    { title: '换手率', dataIndex: 'turnover_rate', render: (v: number) => `${v?.toFixed(2)}%` },
    { title: '原因', dataIndex: 'reason', ellipsis: true }
  ]

  const patternColumns = [
    { title: '形态', dataIndex: 'name' },
    { title: '代码', dataIndex: 'pattern' },
    { title: '匹配数', dataIndex: 'count' },
    { title: '平均涨跌幅', dataIndex: 'avg_change_pct', render: (v: number) => `${v?.toFixed(2)}%` },
    { title: '平均置信度', dataIndex: 'avg_confidence', render: (v: number) => `${(v * 100).toFixed(0)}%` }
  ]

  return (
    <div>
      <Title level={4}><AlertOutlined /> 市场监控</Title>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'signals',
            label: (
              <span>
                <AlertOutlined /> 信号监控
                {unreadCount > 0 && <Badge count={unreadCount} style={{ marginLeft: 8 }} />}
              </span>
            ),
            children: (
              <Card
                title="交易信号"
                extra={
                  <Space>
                    <Button onClick={loadSignals}>刷新</Button>
                    <Button onClick={markAllRead}>全部已读</Button>
                  </Space>
                }
              >
                <Table
                  columns={signalColumns}
                  dataSource={signals}
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 20 }}
                />
              </Card>
            )
          },
          {
            key: 'moneyflow',
            label: <span><FundOutlined /> 主力资金</span>,
            children: (
              <Spin spinning={loading}>
                {flowOverview && (
                  <Row gutter={16} style={{ marginBottom: 16 }}>
                    <Col span={6}>
                      <Card><Statistic title="统计股票数" value={flowOverview.total_stocks} /></Card>
                    </Col>
                    <Col span={6}>
                      <Card><Statistic title="净流入家数" value={flowOverview.inflow_count} prefix={<RiseOutlined />} valueStyle={{ color: '#f5222d' }} /></Card>
                    </Col>
                    <Col span={6}>
                      <Card><Statistic title="净流出家数" value={flowOverview.outflow_count} valueStyle={{ color: '#52c41a' }} /></Card>
                    </Col>
                    <Col span={6}>
                      <Card><Statistic title="主力净流入" value={(flowOverview.net_flow / 100000000).toFixed(2)} suffix="亿" /></Card>
                    </Col>
                  </Row>
                )}
                <Row gutter={16}>
                  <Col span={14}>
                    <Card
                      title="个股主力净流入排名"
                      extra={
                        <Space>
                          <Segmented value={flowPeriod} onChange={(v) => setFlowPeriod(v as string)} options={[{ label: '今日', value: 'today' }, { label: '3日', value: '3d' }, { label: '5日', value: '5d' }]} />
                          <Segmented value={flowDirection} onChange={(v) => setFlowDirection(v as string)} options={[{ label: '流入', value: 'inflow' }, { label: '流出', value: 'outflow' }]} />
                          <Button size="small" onClick={loadMoneyFlow}>刷新</Button>
                        </Space>
                      }
                    >
                      <Table columns={flowColumns} dataSource={flowRank} rowKey="code" size="small" pagination={{ pageSize: 10 }} />
                    </Card>
                  </Col>
                  <Col span={10}>
                    <Card
                      title="概念板块资金流向"
                      extra={<Button size="small" onClick={loadMoneyFlow}>刷新</Button>}
                    >
                      <Table columns={sectorFlowColumns} dataSource={sectorFlow} rowKey="code" size="small" pagination={{ pageSize: 10 }} />
                    </Card>
                  </Col>
                </Row>
              </Spin>
            )
          },
          {
            key: 'lhb',
            label: <span><FireOutlined /> 龙虎榜</span>,
            children: (
              <Spin spinning={loading}>
                <Card
                  title="今日龙虎榜"
                  extra={
                    <Space>
                      <Segmented value={lhbDirection} onChange={(v) => setLhbDirection(v as string)} options={[{ label: '全部', value: 'all' }, { label: '买方主导', value: 'buy' }, { label: '卖方主导', value: 'sell' }]} />
                      <Button size="small" onClick={loadLHB}>刷新</Button>
                    </Space>
                  }
                >
                  <Table columns={lhbColumns} dataSource={lhbList} rowKey="code" size="small" pagination={{ pageSize: 20 }} />
                </Card>
              </Spin>
            )
          },
          {
            key: 'patterns',
            label: <span><BarChartOutlined /> 形态扫描</span>,
            children: (
              <Spin spinning={loading}>
                <Card
                  title="技术形态统计"
                  extra={
                    <Space>
                      <Button type="primary" loading={scanning} onClick={scanPatterns}>全市场扫描</Button>
                      <Button size="small" onClick={loadPatterns}>刷新</Button>
                    </Space>
                  }
                >
                  <Table columns={patternColumns} dataSource={patternStats} rowKey="pattern" size="small" pagination={{ pageSize: 10 }} />
                </Card>
              </Spin>
            )
          }
        ]}
      />
    </div>
  )
}
