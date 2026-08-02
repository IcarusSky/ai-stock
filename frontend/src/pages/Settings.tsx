import { useEffect, useState } from 'react'
import { Card, Form, Input, Button, Switch, Space, message, Typography, Tag, Alert } from 'antd'
import { SaveOutlined, ApiOutlined, BellOutlined, LockOutlined, DatabaseOutlined } from '@ant-design/icons'
import { feishuApi, dataSourceApi, settingsApi } from '../services/api'

const { Title, Text } = Typography

const channelLabel: Record<string, string> = {
  ifind: '同花顺 iFinD（官方）',
  free: 'akshare 免费通道',
  mock: '模拟数据',
}
const channelColor: Record<string, string> = {
  ifind: 'green',
  free: 'blue',
  mock: 'orange',
}

interface DataSourceStatus {
  priority: string
  market_channel: string
  last_channel: string
  ifind: { configured: boolean }
  free: { available: boolean }
  wencai: { available: boolean; channel: string | null }
  tianyancha: { configured: boolean; today_calls: number; daily_limit: number }
}

export default function Settings() {
  const [feishuForm] = Form.useForm()
  const [brokerForm] = Form.useForm()
  const [riskForm] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [testingFeishu, setTestingFeishu] = useState(false)
  const [dsStatus, setDsStatus] = useState<DataSourceStatus | null>(null)
  const [settingsLoaded, setSettingsLoaded] = useState(false)

  // settingsLoaded 用于标记配置是否已加载完成，后续可据此控制骨架屏等

  const loadDsStatus = () => {
    dataSourceApi
      .status()
      .then((res) => setDsStatus(res.data))
      .catch(() => setDsStatus(null))
  }

  const loadSettings = () => {
    settingsApi.get()
      .then((res) => {
        const data = res.data
        if (data.feishu) {
          feishuForm.setFieldsValue(data.feishu)
        }
        if (data.broker) {
          brokerForm.setFieldsValue({
            broker_type: data.broker.broker_type || 'pingan',
            app_id: data.broker.app_id || '',
            app_secret: data.broker.app_secret?.includes('*') ? '' : (data.broker.app_secret || ''),
          })
        }
        if (data.risk) {
          riskForm.setFieldsValue({
            max_position_ratio: (data.risk.max_position_ratio ?? 0.2) * 100,
            max_total_positions: data.risk.max_total_positions ?? 5,
            stop_loss_ratio: (data.risk.stop_loss_ratio ?? 0.05) * 100,
            daily_loss_limit: (data.risk.daily_loss_limit ?? 0.015) * 100,
            min_trade_amount: data.risk.min_trade_amount ?? 2000,
          })
        }
        setSettingsLoaded(true)
      })
      .catch(() => {
        message.warning('加载系统配置失败')
        setSettingsLoaded(true)
      })
  }

  useEffect(() => {
    loadDsStatus()
    loadSettings()
  }, [])

  const saveFeishu = async () => {
    setSaving(true)
    try {
      const values = feishuForm.getFieldsValue()
      await settingsApi.saveFeishu(values)
      message.success('飞书设置已保存')
    } catch (error) {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const testFeishu = async () => {
    setTestingFeishu(true)
    try {
      const res = await feishuApi.test()
      if (res.data.success) {
        message.success('飞书连接测试成功!')
      } else {
        message.error('飞书连接测试失败')
      }
    } catch (error) {
      message.error('飞书连接测试失败')
    } finally {
      setTestingFeishu(false)
    }
  }

  const saveBroker = async () => {
    const values = brokerForm.getFieldsValue()
    try {
      await settingsApi.saveBroker(values)
      message.success('券商配置已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  const saveRisk = async () => {
    const values = riskForm.getFieldsValue()
    try {
      await settingsApi.saveRisk({
        max_position_ratio: values.max_position_ratio / 100,
        max_total_positions: values.max_total_positions,
        stop_loss_ratio: values.stop_loss_ratio / 100,
        daily_loss_limit: values.daily_loss_limit / 100,
        min_trade_amount: values.min_trade_amount,
      })
      message.success('风控设置已保存')
    } catch (error) {
      message.error('保存失败')
    }
  }

  return (
    <div>
      <Title level={4}>⚙️ 系统设置</Title>

      {/* 数据源与 API 状态 */}
      <Card
        title={<Space><DatabaseOutlined /> 数据源与 API</Space>}
        style={{ marginBottom: 16 }}
        extra={<Button size="small" onClick={loadDsStatus}>刷新</Button>}
      >
        <Alert
          message="数据源 token 在 backend/.env 中配置，修改后重启后端生效"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        {dsStatus ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {settingsLoaded && null}
            <div>
              <Text strong>行情通道：</Text>
              <Tag color={channelColor[dsStatus.market_channel] || 'default'}>
                {channelLabel[dsStatus.market_channel] || dsStatus.market_channel}
              </Tag>
              <Text type="secondary">优先级策略：{dsStatus.priority}，最近取数：{channelLabel[dsStatus.last_channel] || dsStatus.last_channel}</Text>
            </div>
            <div>
              <Text strong>同花顺 iFinD：</Text>
              {dsStatus.ifind?.configured ? (
                <Tag color="green">已配置</Tag>
              ) : (
                <Tag>未配置</Tag>
              )}
              <Text type="secondary">在 backend/.env 配置 IFIND_REFRESH_TOKEN 后启用官方通道</Text>
            </div>
            <div>
              <Text strong>天眼查：</Text>
              {dsStatus.tianyancha?.configured ? (
                <Tag color="green">已配置</Tag>
              ) : (
                <Tag>未配置</Tag>
              )}
              <Text type="secondary">
                当日用量 {dsStatus.tianyancha?.today_calls ?? 0}/{dsStatus.tianyancha?.daily_limit ?? '-'} 次（按次计费）
              </Text>
            </div>
            <div>
              <Text strong>问财选股：</Text>
              {dsStatus.wencai?.available ? (
                <Tag color="green">已启用（{dsStatus.wencai.channel}）</Tag>
              ) : (
                <Tag>未启用</Tag>
              )}
            </div>
          </Space>
        ) : (
          <Alert message="无法获取数据源状态，请确认后端已启动" type="warning" showIcon />
        )}
      </Card>

      {/* 飞书推送设置 */}
      <Card
        title={<Space><BellOutlined /> 飞书推送设置</Space>}
        style={{ marginBottom: 16 }}
        extra={<Tag color="green">已配置</Tag>}
      >
        <Form form={feishuForm} layout="vertical" initialValues={{ webhook_url: '' }}>
          <Form.Item name="webhook_url" label="飞书Webhook地址">
            <Input placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx" />
          </Form.Item>
          <Form.Item name="enable_trade_signal" label="交易信号推送" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Form.Item name="enable_position_change" label="持仓变动通知" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Form.Item name="enable_risk_alert" label="风险预警通知" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Form.Item name="enable_daily_report" label="每日报告推送" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Space>
            <Button type="primary" icon={<SaveOutlined />} onClick={saveFeishu} loading={saving}>保存</Button>
            <Button icon={<ApiOutlined />} onClick={testFeishu} loading={testingFeishu}>测试连接</Button>
          </Space>
        </Form>
      </Card>

      {/* 券商对接设置 */}
      <Card
        title={<Space><LockOutlined /> 券商对接设置</Space>}
        style={{ marginBottom: 16 }}
      >
        <Alert
          message="券商对接说明"
          description="当前使用模拟账户进行交易。如需对接实盘，请联系管理员配置券商API。"
          type="info"
          style={{ marginBottom: 16 }}
        />
        <Form form={brokerForm} layout="vertical" initialValues={{ broker_type: 'pingan' }}>
          <Form.Item name="broker_type" label="券商">
            <Input placeholder="平安证券" disabled />
          </Form.Item>
          <Form.Item name="app_id" label="App ID">
            <Input placeholder="请输入券商App ID" />
          </Form.Item>
          <Form.Item name="app_secret" label="App Secret">
            <Input.Password placeholder="请输入券商App Secret" />
          </Form.Item>
          <Button type="primary" onClick={saveBroker}>保存券商配置</Button>
        </Form>
      </Card>

      {/* 风控设置 */}
      <Card title="风控设置" style={{ marginBottom: 16 }}>
        <Form form={riskForm} layout="vertical" initialValues={{
          max_position_ratio: 20,
          max_total_positions: 5,
          stop_loss_ratio: 5,
          daily_loss_limit: 1.5,
          min_trade_amount: 2000
        }}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <Space>
              <Form.Item name="max_position_ratio" label="单只股票最大仓位比例" style={{ marginBottom: 0 }}>
                <Input type="number" suffix="%" style={{ width: 100 }} />
              </Form.Item>
              <Text type="secondary">单只股票持仓不超过总资金的20%</Text>
            </Space>

            <Space>
              <Form.Item name="max_total_positions" label="最大持仓数量" style={{ marginBottom: 0 }}>
                <Input type="number" style={{ width: 100 }} />
              </Form.Item>
              <Text type="secondary">同时持有不超过5只股票</Text>
            </Space>

            <Space>
              <Form.Item name="stop_loss_ratio" label="止损比例" style={{ marginBottom: 0 }}>
                <Input type="number" suffix="%" style={{ width: 100 }} />
              </Form.Item>
              <Text type="secondary">亏损超过5%必须止损</Text>
            </Space>

            <Space>
              <Form.Item name="daily_loss_limit" label="每日最大亏损" style={{ marginBottom: 0 }}>
                <Input type="number" suffix="%" style={{ width: 100 }} />
              </Form.Item>
              <Text type="secondary">当日亏损超过1.5%停止交易</Text>
            </Space>

            <Space>
              <Form.Item name="min_trade_amount" label="最小交易金额" style={{ marginBottom: 0 }}>
                <Input type="number" suffix="元" style={{ width: 120 }} />
              </Form.Item>
              <Text type="secondary">避免佣金占比过高</Text>
            </Space>
          </Space>
          <Button type="primary" onClick={saveRisk} style={{ marginTop: 16 }}>保存风控设置</Button>
        </Form>
      </Card>
    </div>
  )
}
