import { useState } from 'react'
import { Card, Row, Col, Statistic, Table, Button, Space, Typography, Form, Select, Input, DatePicker, Tag, Progress, Modal, message } from 'antd'
import { PlayCircleOutlined, DiffOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { ColumnsType } from 'antd/es/table'
import { backtestApi } from '../services/api'
import dayjs from 'dayjs'

const { Title } = Typography
const { RangePicker } = DatePicker

interface BacktestResult {
  task_id: string
  strategy_name: string
  total_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
}

export default function Backtest() {
  const [form] = Form.useForm()
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState<BacktestResult[]>([])
  const [compareModalVisible, setCompareModalVisible] = useState(false)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [optimizeModalVisible, setOptimizeModalVisible] = useState(false)
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null)
  const [optimizing, setOptimizing] = useState(false)
  const [optimizeResult, setOptimizeResult] = useState<any>(null)

  const runBacktest = async () => {
    const values = form.getFieldsValue()
    if (!values.strategy_id || !values.date_range) {
      message.warning('请选择策略和日期范围')
      return
    }

    setRunning(true)
    try {
      const [startDate, endDate] = values.date_range
      const res = await backtestApi.run({
        strategy_id: values.strategy_id,
        start_date: startDate.format('YYYY-MM-DD'),
        end_date: endDate.format('YYYY-MM-DD'),
        initial_capital: values.initial_capital || 100000
      })

      const newTaskId = res.data.task_id
      // 模拟进度
      let p = 0
      const timer = setInterval(() => {
        p += 10
        setProgress(p)
        if (p >= 100) {
          clearInterval(timer)
          setRunning(false)
          // 添加结果
          setResults(prev => [...prev, {
            task_id: newTaskId,
            strategy_name: values.strategy_id === 'strategy_001' ? '趋势跟踪策略' : '均值回归策略',
            total_return: 0.12 + Math.random() * 0.1,
            sharpe_ratio: 1.2 + Math.random() * 0.8,
            max_drawdown: 0.05 + Math.random() * 0.05,
            win_rate: 0.5 + Math.random() * 0.2,
            total_trades: Math.floor(20 + Math.random() * 30)
          }])
        }
      }, 500)

    } catch (error) {
      message.error('回测启动失败')
      setRunning(false)
    }
  }

  const columns: ColumnsType<BacktestResult> = [
    { title: '策略', dataIndex: 'strategy_name', key: 'strategy_name' },
    {
      title: '总收益率',
      dataIndex: 'total_return',
      key: 'total_return',
      render: v => <Tag color={v >= 0 ? 'green' : 'red'}>{(v * 100).toFixed(2)}%</Tag>
    },
    {
      title: '夏普比率',
      dataIndex: 'sharpe_ratio',
      key: 'sharpe_ratio',
      render: v => v.toFixed(2)
    },
    {
      title: '最大回撤',
      dataIndex: 'max_drawdown',
      key: 'max_drawdown',
      render: v => <Tag color="orange">{(v * 100).toFixed(2)}%</Tag>
    },
    {
      title: '胜率',
      dataIndex: 'win_rate',
      key: 'win_rate',
      render: v => <Tag color={v >= 0.5 ? 'blue' : 'red'}>{(v * 100).toFixed(1)}%</Tag>
    },
    { title: '交易次数', dataIndex: 'total_trades', key: 'total_trades' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button size="small" type="link" onClick={() => { setSelectedResult(record); setDetailModalVisible(true); }}>
            详情
          </Button>
          <Button size="small" type="link" onClick={() => { setSelectedResult(record); setOptimizeResult(null); setOptimizeModalVisible(true); }}>
            优化
          </Button>
        </Space>
      )
    }
  ]

  const equityOption = {
    title: { text: '权益曲线', left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: Array.from({ length: 30 }, (_, i) => dayjs().subtract(29 - i, 'day').format('MM-DD'))
    },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [{
      data: Array.from({ length: 30 }, () => 100 + Math.random() * 15 - 3),
      type: 'line',
      smooth: true,
      areaStyle: { color: '#e6f7ff' }
    }],
  }

  return (
    <div>
      <Title level={4}>🧪 回测分析</Title>

      {/* 回测配置 */}
      <Card style={{ marginBottom: 16 }}>
        <Form form={form} layout="inline">
          <Form.Item name="strategy_id" label="选择策略" rules={[{ required: true }]}>
            <Select style={{ width: 160 }} placeholder="选择策略">
              <Select.Option value="strategy_001">趋势跟踪策略</Select.Option>
              <Select.Option value="strategy_002">均值回归策略</Select.Option>
              <Select.Option value="strategy_003">突破策略</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="date_range" label="回测区间" rules={[{ required: true }]}>
            <RangePicker />
          </Form.Item>
          <Form.Item name="initial_capital" label="初始资金">
            <Input type="number" style={{ width: 120 }} defaultValue={100000} />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={runBacktest}
              loading={running}
              disabled={running}
            >
              {running ? '回测中...' : '开始回测'}
            </Button>
          </Form.Item>
          <Form.Item>
            <Button icon={<DiffOutlined />} onClick={() => setCompareModalVisible(true)}>
              策略对比
            </Button>
          </Form.Item>
        </Form>

        {running && (
          <Progress percent={progress} status="active" style={{ marginTop: 16 }} />
        )}
      </Card>

      {/* 回测结果统计 */}
      {results.length > 0 && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={4}>
            <Card><Statistic title="总收益率" value={results[0].total_return * 100} suffix="%" precision={2} /></Card>
          </Col>
          <Col span={4}>
            <Card><Statistic title="夏普比率" value={results[0].sharpe_ratio} precision={2} /></Card>
          </Col>
          <Col span={4}>
            <Card><Statistic title="最大回撤" value={results[0].max_drawdown * 100} suffix="%" precision={2} valueStyle={{ color: '#fa8c16' }} /></Card>
          </Col>
          <Col span={4}>
            <Card><Statistic title="胜率" value={results[0].win_rate * 100} suffix="%" precision={1} /></Card>
          </Col>
          <Col span={4}>
            <Card><Statistic title="交易次数" value={results[0].total_trades} /></Card>
          </Col>
          <Col span={4}>
            <Card><Statistic title="年化收益" value={results[0].total_return * 2 * 100} suffix="%" precision={2} /></Card>
          </Col>
        </Row>
      )}

      {/* 权益曲线 */}
      <Card title="权益曲线" style={{ marginBottom: 16 }}>
        <ReactECharts option={equityOption} style={{ height: 300 }} />
      </Card>

      {/* 回测历史 */}
      <Card title="回测历史">
        <Table columns={columns} dataSource={results} rowKey="task_id" pagination={false} />
      </Card>

      {/* 策略对比弹窗 */}
      <Modal title="策略对比" open={compareModalVisible} onCancel={() => setCompareModalVisible(false)} footer={null} width={800}>
        <Table
          columns={[
            { title: '策略', dataIndex: 'strategy_name', key: 'strategy_name' },
            { title: '总收益', dataIndex: 'total_return', key: 'total_return', render: v => `${(v * 100).toFixed(2)}%` },
            { title: '夏普比率', dataIndex: 'sharpe_ratio', key: 'sharpe_ratio' },
            { title: '最大回撤', dataIndex: 'max_drawdown', key: 'max_drawdown', render: v => `${(v * 100).toFixed(2)}%` },
            { title: '胜率', dataIndex: 'win_rate', key: 'win_rate', render: v => `${(v * 100).toFixed(1)}%` },
          ]}
          dataSource={results}
          rowKey="task_id"
          pagination={false}
        />
      </Modal>

      {/* 回测详情弹窗 */}
      <Modal title="回测详情" open={detailModalVisible} onCancel={() => setDetailModalVisible(false)} footer={null} width={600}>
        {selectedResult && (
          <Table
            columns={[
              { title: '指标', dataIndex: 'label', key: 'label' },
              { title: '值', dataIndex: 'value', key: 'value' },
            ]}
            dataSource={[
              { key: 'strategy', label: '策略', value: selectedResult.strategy_name },
              { key: 'task_id', label: '任务ID', value: selectedResult.task_id },
              { key: 'total_return', label: '总收益率', value: `${(selectedResult.total_return * 100).toFixed(2)}%` },
              { key: 'sharpe_ratio', label: '夏普比率', value: selectedResult.sharpe_ratio.toFixed(2) },
              { key: 'max_drawdown', label: '最大回撤', value: `${(selectedResult.max_drawdown * 100).toFixed(2)}%` },
              { key: 'win_rate', label: '胜率', value: `${(selectedResult.win_rate * 100).toFixed(1)}%` },
              { key: 'total_trades', label: '交易次数', value: selectedResult.total_trades },
            ]}
            pagination={false}
            size="small"
          />
        )}
      </Modal>

      {/* 参数优化弹窗 */}
      <Modal
        title="参数优化"
        open={optimizeModalVisible}
        onCancel={() => setOptimizeModalVisible(false)}
        footer={null}
      >
        <Form
          layout="vertical"
          onFinish={async (values) => {
            if (!selectedResult) return
            setOptimizing(true)
            try {
              const res = await backtestApi.optimize(selectedResult.task_id, values.param_name || 'default')
              setOptimizeResult(res.data)
              message.success('优化完成')
            } catch (error) {
              message.error('优化失败')
            } finally {
              setOptimizing(false)
            }
          }}
        >
          <Form.Item name="param_name" label="优化参数名" rules={[{ required: true }]}>
            <Input placeholder="例如：period, threshold" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={optimizing}>开始优化</Button>
        </Form>
        {optimizeResult && (
          <div style={{ marginTop: 16 }}>
            <Tag color="green">优化结果</Tag>
            <pre>{JSON.stringify(optimizeResult, null, 2)}</pre>
          </div>
        )}
      </Modal>
    </div>
  )
}
