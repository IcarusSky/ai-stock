import { useState, useEffect } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Modal, Form, Input, Select, message, Tabs, List, Badge, Descriptions } from 'antd'
import { ThunderboltOutlined, BuildOutlined, PlusOutlined, ExperimentOutlined, CheckOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { strategyApi } from '../services/api'

const { Title, Text } = Typography

interface Strategy {
  id: string
  name: string
  type: string
  description: string
  params: any
  status: string
}

export default function Strategy() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [dailyRecommend, setDailyRecommend] = useState<any>(null)
  const [marketEnv, setMarketEnv] = useState<any>(null)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [llmModalVisible, setLlmModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [editingStrategy, setEditingStrategy] = useState<Strategy | null>(null)
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null)
  const [editForm] = Form.useForm()
  const [createForm] = Form.useForm()
  const [llmForm] = Form.useForm()
  const [loading, setLoading] = useState(false)

  const loadStrategies = async () => {
    try {
      const res = await strategyApi.list()
      setStrategies(res.data)
    } catch (error) {
      console.error('加载策略失败:', error)
    }
  }

  const loadDailyRecommend = async () => {
    try {
      const res = await strategyApi.getDailyRecommend()
      setDailyRecommend(res.data)
      setMarketEnv(res.data.market_env)
    } catch (error) {
      console.error('加载每日推荐失败:', error)
    }
  }

  useEffect(() => {
    loadStrategies()
    loadDailyRecommend()
  }, [])

  const handleLLMStrategy = async () => {
    const description = llmForm.getFieldValue('description')
    if (!description) {
      message.warning('请描述您的策略')
      return
    }

    setLoading(true)
    try {
      await strategyApi.register({
        name: 'AI生成策略',
        type: 'TREND_FOLLOWING',
        description,
        params: {}
      })
      message.success('策略生成成功')
      setLlmModalVisible(false)
      llmForm.resetFields()
      loadStrategies()
    } catch (error) {
      message.error('策略生成失败')
    } finally {
      setLoading(false)
    }
  }

  const applyStrategy = async (strategy: Strategy) => {
    try {
      await strategyApi.update(strategy.id, { status: 'ACTIVE' })
      message.success(`策略「${strategy.name}」已启用`)
      loadStrategies()
    } catch (error) {
      message.error('启用失败')
    }
  }

  const handleEditStrategy = async (values: any) => {
    if (!editingStrategy) return
    try {
      await strategyApi.update(editingStrategy.id, values)
      message.success('策略更新成功')
      setEditModalVisible(false)
      loadStrategies()
    } catch (error) {
      message.error('更新失败')
    }
  }

  const handleDeleteStrategy = (strategy: Strategy) => {
    Modal.confirm({
      title: '确认删除策略',
      content: `确定删除策略「${strategy.name}」吗？`,
      onOk: async () => {
        try {
          await strategyApi.delete(strategy.id)
          message.success('删除成功')
          loadStrategies()
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  const columns: ColumnsType<Strategy> = [
    { title: '策略名称', dataIndex: 'name', key: 'name' },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => {
        const colors: Record<string, string> = {
          TREND_FOLLOWING: 'blue',
          MEAN_REVERSION: 'green',
          BREAKTHROUGH: 'purple',
          SECTOR_ROTATION: 'orange',
          VALUE_INVESTMENT: 'cyan'
        }
        const names: Record<string, string> = {
          TREND_FOLLOWING: '趋势跟踪',
          MEAN_REVERSION: '均值回归',
          BREAKTHROUGH: '突破策略',
          SECTOR_ROTATION: '板块轮动',
          VALUE_INVESTMENT: '价值投资'
        }
        return <Tag color={colors[type]}>{names[type] || type}</Tag>
      }
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Badge status={s === 'ACTIVE' ? 'success' : 'default'} text={s === 'ACTIVE' ? '启用' : '停用'} />
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button size="small" type="link" onClick={() => { setSelectedStrategy(record); setDetailModalVisible(true); }}>
            查看
          </Button>
          <Button size="small" type="link" onClick={() => { setEditingStrategy(record); editForm.setFieldsValue(record); setEditModalVisible(true); }}>
            编辑
          </Button>
          <Button size="small" danger type="link" onClick={() => handleDeleteStrategy(record)}>
            删除
          </Button>
        </Space>
      )
    }
  ]

  const strategyTypeOptions = [
    { value: 'TREND_FOLLOWING', label: '趋势跟踪' },
    { value: 'MEAN_REVERSION', label: '均值回归' },
    { value: 'BREAKTHROUGH', label: '突破策略' },
    { value: 'SECTOR_ROTATION', label: '板块轮动' },
    { value: 'VALUE_INVESTMENT', label: '价值投资' },
  ]

  return (
    <div>
      <Title level={4}>⚙️ 策略管理</Title>

      {/* 市场环境和策略推荐 */}
      <Card style={{ marginBottom: 16 }}>
        <Space size="large">
          <div>
            <Text type="secondary">市场趋势：</Text>
            <Tag color={marketEnv?.trend === 'BULL' ? 'green' : marketEnv?.trend === 'BEAR' ? 'red' : 'default'}>
              {marketEnv?.trend === 'BULL' ? '多头' : marketEnv?.trend === 'BEAR' ? '空头' : '震荡'}
            </Tag>
          </div>
          <div>
            <Text type="secondary">波动率：</Text>
            <Tag>{marketEnv?.volatility || '中'}</Tag>
          </div>
          <div>
            <Text type="secondary">成交量：</Text>
            <Tag>{marketEnv?.volume || '中'}</Tag>
          </div>
          <div>
            <Text type="secondary">整体判断：</Text>
            <Tag color={marketEnv?.overall === 'OPTIMISTIC' ? 'green' : marketEnv?.overall === 'PESSIMISTIC' ? 'red' : 'default'}>
              {marketEnv?.overall === 'OPTIMISTIC' ? '乐观' : marketEnv?.overall === 'PESSIMISTIC' ? '悲观' : '中性'}
            </Tag>
          </div>
          <div>
            <Text type="secondary">环境评分：</Text>
            <Text strong>{marketEnv?.score?.toFixed(0) || 50}/100</Text>
          </div>
        </Space>
      </Card>

      <Tabs
        defaultActiveKey="list"
        items={[
          {
            key: 'list',
            label: <span><BuildOutlined /> 策略列表</span>,
            children: (
              <Card extra={
                <Space>
                  <Button icon={<ExperimentOutlined />} onClick={() => setLlmModalVisible(true)}>
                    AI生成策略
                  </Button>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
                    新建策略
                  </Button>
                </Space>
              }>
                <Table
                  columns={columns}
                  dataSource={strategies}
                  rowKey="id"
                  pagination={{ pageSize: 10 }}
                />
              </Card>
            )
          },
          {
            key: 'daily',
            label: <span><ThunderboltOutlined /> 每日推荐</span>,
            children: (
              <Card>
                <Title level={5}>今日推荐策略</Title>
                <List
                  dataSource={dailyRecommend?.recommended_strategies || []}
                  renderItem={(item: any) => (
                    <List.Item>
                      <List.Item.Meta
                        title={item.name}
                        description={`权重: ${(item.weight * 100).toFixed(0)}%`}
                      />
                      <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => applyStrategy(item)}>应用此策略</Button>
                    </List.Item>
                  )}
                />
                {dailyRecommend?.trading_plan && (
                  <>
                    <Title level={5} style={{ marginTop: 24 }}>交易计划</Title>
                    <div style={{ background: '#f5f5f5', padding: 16, borderRadius: 8 }}>
                      <p><strong>仓位建议：</strong>{dailyRecommend.trading_plan.仓位建议}</p>
                      <p><strong>重点关注：</strong>{dailyRecommend.trading_plan.重点关注?.join(', ')}</p>
                      <p><strong>风险提示：</strong>{dailyRecommend.trading_plan.风险提示}</p>
                    </div>
                  </>
                )}
              </Card>
            )
          }
        ]}
      />

      {/* 新建策略弹窗 */}
      <Modal title="新建策略" open={createModalVisible} onCancel={() => setCreateModalVisible(false)} footer={null}>
        <Form form={createForm} layout="vertical" onFinish={(values) => {
          strategyApi.register(values).then(() => {
            message.success('策略创建成功')
            setCreateModalVisible(false)
            createForm.resetFields()
            loadStrategies()
          }).catch(() => message.error('创建失败'))
        }}>
          <Form.Item name="name" label="策略名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="策略类型" rules={[{ required: true }]}>
            <Select options={strategyTypeOptions} />
          </Form.Item>
          <Form.Item name="description" label="策略描述">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Button type="primary" htmlType="submit">创建策略</Button>
        </Form>
      </Modal>

      {/* LLM生成策略弹窗 */}
      <Modal title="🤖 AI策略生成" open={llmModalVisible} onCancel={() => setLlmModalVisible(false)} footer={null}>
        <Form form={llmForm} layout="vertical">
          <Form.Item label="描述你的策略">
            <Input.TextArea
              rows={4}
              placeholder="例如：当MACD金叉且成交量放大时买入，当价格跌破20日均线时卖出"
            />
          </Form.Item>
          <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
            提示：描述越详细，生成的策略越准确
          </Text>
          <Button type="primary" onClick={handleLLMStrategy} loading={loading}>
            生成策略
          </Button>
        </Form>
      </Modal>

      {/* 编辑策略弹窗 */}
      <Modal
        title="编辑策略"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        footer={null}
      >
        <Form form={editForm} layout="vertical" onFinish={handleEditStrategy}>
          <Form.Item name="name" label="策略名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="策略类型" rules={[{ required: true }]}>
            <Select options={strategyTypeOptions} />
          </Form.Item>
          <Form.Item name="description" label="策略描述">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading}>保存</Button>
        </Form>
      </Modal>

      {/* 策略详情弹窗 */}
      <Modal
        title="策略详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
      >
        {selectedStrategy && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="策略名称">{selectedStrategy.name}</Descriptions.Item>
            <Descriptions.Item label="类型">{selectedStrategy.type}</Descriptions.Item>
            <Descriptions.Item label="描述">{selectedStrategy.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="状态">{selectedStrategy.status === 'ACTIVE' ? '启用' : '停用'}</Descriptions.Item>
            <Descriptions.Item label="参数">{JSON.stringify(selectedStrategy.params) || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
