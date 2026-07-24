import { useState, useEffect } from 'react'
import {
  Row, Col, Card, Statistic, Table, Tag, Space, Button, Modal, Form, Input,
  InputNumber, message, Alert, Typography
} from 'antd'
import {
  RiseOutlined, FallOutlined, DollarOutlined, BankOutlined,
  AlertOutlined, PlusOutlined, SyncOutlined
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { ColumnsType } from 'antd/es/table'
import { marketApi, portfolioApi, orderApi } from '../services/api'

const { Title, Text } = Typography

interface Position {
  code: string
  name: string
  quantity: number
  avg_cost: number
  current_price: number
  profit_loss: number
  profit_rate: number
}

interface Quote {
  code: string
  name: string
  price: number
  change: number
  change_pct: number
}

export default function Dashboard() {
  const [positions, setPositions] = useState<Position[]>([])
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const [watchlist, setWatchlist] = useState<any[]>([])
  const [account, setAccount] = useState<any>({})
  const [capitalCurve, setCapitalCurve] = useState<any[]>([])
  const [orderModalVisible, setOrderModalVisible] = useState(false)
  const [orderForm] = Form.useForm()
  const [selectedStock, setSelectedStock] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [addWatchModalVisible, setAddWatchModalVisible] = useState(false)
  const [watchCode, setWatchCode] = useState('')

  // 加载数据
  const loadData = async () => {
    try {
      const [positionsRes, watchlistRes, accountRes, curveRes] = await Promise.all([
        portfolioApi.getPositions(),
        marketApi.getWatchlist(),
        portfolioApi.getAccount(),
        portfolioApi.getCapitalCurve(30),
      ])

      setPositions(positionsRes.data)
      setWatchlist(watchlistRes.data)
      setAccount(accountRes.data)
      setCapitalCurve(curveRes.data)

      // 获取自选股行情
      const codes = watchlistRes.data.map((w: any) => w.code)
      if (codes.length > 0) {
        const quotesRes = await marketApi.getQuotes(codes)
        const quoteMap: Record<string, Quote> = {}
        quotesRes.data.forEach((q: Quote) => {
          quoteMap[q.code] = q
        })
        setQuotes(quoteMap)
      }
    } catch (error) {
      console.error('加载数据失败:', error)
    }
  }

  useEffect(() => {
    loadData()
    // 每30秒刷新一次
    const timer = setInterval(loadData, 30000)
    return () => clearInterval(timer)
  }, [])

  // 资金曲线配置
  const getCapitalCurveOption = () => {
    const dates = capitalCurve.map(c => c.date)
    const values = capitalCurve.map(c => c.total_value)

    return {
      title: { text: '资金曲线', left: 'center' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: dates },
      yAxis: { type: 'value', axisLabel: { formatter: '{value} 元' } },
      series: [{
        data: values,
        type: 'line',
        smooth: true,
        areaStyle: { color: '#e6f7ff' },
        lineStyle: { color: '#1890ff', width: 2 },
      }],
    }
  }

  // 下单
  const handleOrder = async (values: any) => {
    setLoading(true)
    try {
      const api = values.direction === 'BUY' ? orderApi.buy : orderApi.sell
      const res = await api({
        stock_code: selectedStock.code,
        direction: values.direction,
        order_type: 'LIMIT',
        price: values.price,
        quantity: values.quantity
      })

      if (res.data.status === 'FILLED') {
        message.success(`${values.direction === 'BUY' ? '买入' : '卖出'}成功`)
        setOrderModalVisible(false)
        orderForm.resetFields()
        loadData()
      } else {
        message.error(res.data.message || '下单失败')
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '下单失败')
    } finally {
      setLoading(false)
    }
  }

  const openOrderModal = (stock: any, direction: 'BUY' | 'SELL') => {
    setSelectedStock({ ...stock, direction })
    orderForm.setFieldsValue({
      stock_code: stock.code,
      stock_name: stock.name,
      direction,
      price: quotes[stock.code]?.price || 0,
      quantity: 100
    })
    setOrderModalVisible(true)
  }

  const handleAddWatchlist = async () => {
    if (!watchCode.trim()) {
      message.warning('请输入股票代码')
      return
    }
    try {
      await marketApi.addToWatchlist(watchCode.trim())
      message.success(`已添加 ${watchCode} 到自选`)
      setAddWatchModalVisible(false)
      setWatchCode('')
      loadData()
    } catch (error) {
      message.error('添加失败，请检查股票代码')
    }
  }

  const columns: ColumnsType<Position> = [
    { title: '股票', dataIndex: 'name', key: 'name', render: (name, r) => `${name}(${r.code})` },
    { title: '持股数量', dataIndex: 'quantity', key: 'quantity' },
    {
      title: '成本价', dataIndex: 'avg_cost', key: 'avg_cost',
      render: v => v.toFixed(2)
    },
    {
      title: '现价', dataIndex: 'current_price', key: 'current_price',
      render: v => v?.toFixed(2) || '-'
    },
    {
      title: '盈亏金额', dataIndex: 'profit_loss', key: 'profit_loss',
      render: v => (
        <Text type={v >= 0 ? 'danger' : 'success'}>
          {v >= 0 ? '+' : ''}{v?.toFixed(2)}
        </Text>
      )
    },
    {
      title: '盈亏比例', dataIndex: 'profit_rate', key: 'profit_rate',
      render: v => (
        <Tag color={v >= 0 ? 'red' : 'green'}>
          {v >= 0 ? '+' : ''}{(v * 100)?.toFixed(2)}%
        </Tag>
      )
    },
    {
      title: '操作', key: 'action', render: (_, r) => (
        <Space>
          <Button size="small" type="primary" onClick={() => openOrderModal(r, 'BUY')}>加仓</Button>
          <Button size="small" danger onClick={() => openOrderModal(r, 'SELL')}>减仓</Button>
        </Space>
      )
    }
  ]

  const watchlistColumns = [
    { title: '股票', dataIndex: 'name', key: 'name', render: (name: string, r: any) => `${name}(${r.code})` },
    {
      title: '现价',
      key: 'price',
      render: (_: any, r: any) => {
        const q = quotes[r.code]
        if (!q) return '-'
        return (
          <Text type={q.change_pct >= 0 ? 'danger' : 'success'}>
            {q.price?.toFixed(2)}
          </Text>
        )
      }
    },
    {
      title: '涨跌幅',
      key: 'change_pct',
      render: (_: any, r: any) => {
        const q = quotes[r.code]
        if (!q) return '-'
        return (
          <Tag color={q.change_pct >= 0 ? 'red' : 'green'}>
            {q.change_pct >= 0 ? '+' : ''}{q.change_pct?.toFixed(2)}%
          </Tag>
        )
      }
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[]) => tags?.map(t => <Tag key={t}>{t}</Tag>)
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, r: any) => (
        <Space>
          <Button size="small" type="primary" onClick={() => openOrderModal(r, 'BUY')}>买入</Button>
        </Space>
      )
    }
  ]

  return (
    <div>
      <Title level={4}>📊 实时行情</Title>

      {/* 账户统计 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总资产"
              value={account.total_assets}
              prefix={<DollarOutlined />}
              precision={2}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="可用资金"
              value={account.available_cash}
              prefix={<BankOutlined />}
              precision={2}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="持仓市值"
              value={account.market_value}
              precision={2}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日盈亏"
              value={account.today_profit}
              precision={2}
              prefix={account.today_profit >= 0 ? <RiseOutlined /> : <FallOutlined />}
              valueStyle={{ color: account.today_profit >= 0 ? '#f5222d' : '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 持仓和重点关注 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card title="当前持仓" extra={<Button icon={<SyncOutlined spin={loading} />} onClick={loadData}>刷新</Button>}>
            <Table
              columns={columns}
              dataSource={positions}
              rowKey="code"
              size="small"
              pagination={false}
              locale={{ emptyText: '暂无持仓' }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="重点关注" extra={<Button icon={<PlusOutlined />} type="link" onClick={() => setAddWatchModalVisible(true)}>添加自选</Button>}>
            <Table
              columns={watchlistColumns}
              dataSource={watchlist}
              rowKey="code"
              size="small"
              pagination={false}
            />
          </Card>
        </Col>
      </Row>

      {/* 资金曲线 */}
      <Card title="资金曲线（近30日）">
        <ReactECharts option={getCapitalCurveOption()} style={{ height: 300 }} />
      </Card>

      {/* 风险提示 */}
      <Alert
        type="warning"
        showIcon
        icon={<AlertOutlined />}
        message="风险提示"
        description="本系统仅供辅助参考，炒股有风险，入市需谨慎！初始资金10万，建议单只股票仓位不超过20%（2万），止损线5%。"
        style={{ marginTop: 24 }}
      />

      {/* 下单弹窗 */}
      <Modal
        title={`${selectedStock?.direction === 'BUY' ? '买入' : '卖出'} ${selectedStock?.name || ''}`}
        open={orderModalVisible}
        onCancel={() => setOrderModalVisible(false)}
        footer={null}
      >
        <Form form={orderForm} onFinish={handleOrder} layout="vertical">
          <Form.Item name="stock_code" label="股票代码">
            <Input disabled />
          </Form.Item>
          <Form.Item name="direction" label="方向">
            <Input disabled value={selectedStock?.direction === 'BUY' ? '买入' : '卖出'} />
          </Form.Item>
          <Form.Item
            name="price"
            label="价格"
            rules={[{ required: true, message: '请输入价格' }]}
          >
            <InputNumber style={{ width: '100%' }} min={0.01} precision={2} />
          </Form.Item>
          <Form.Item
            name="quantity"
            label="数量（A股100的整数倍）"
            rules={[{ required: true, message: '请输入数量' }]}
          >
            <InputNumber style={{ width: '100%' }} min={100} step={100} />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={loading}>
              确认{selectedStock?.direction === 'BUY' ? '买入' : '卖出'}
            </Button>
            <Button onClick={() => setOrderModalVisible(false)}>取消</Button>
          </Space>
        </Form>
      </Modal>

      {/* 添加自选弹窗 */}
      <Modal
        title="添加自选"
        open={addWatchModalVisible}
        onCancel={() => { setAddWatchModalVisible(false); setWatchCode(''); }}
        footer={null}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="请输入股票代码，如 000001"
            value={watchCode}
            onChange={e => setWatchCode(e.target.value)}
            onPressEnter={handleAddWatchlist}
          />
          <Button type="primary" onClick={handleAddWatchlist} block>确认添加</Button>
        </Space>
      </Modal>
    </div>
  )
}
