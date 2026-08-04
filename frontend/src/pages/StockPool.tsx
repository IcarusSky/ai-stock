import { useEffect, useState, useRef } from 'react'
import {
  Card, Row, Col, Tree, Table, Button, Space, Tabs, Tag, Input, Modal, message,
  Transfer, Spin, Typography, Popconfirm, Form, Select
} from 'antd'
import {
  DatabaseOutlined, SyncOutlined, PlusOutlined, DeleteOutlined,
  ApartmentOutlined, FolderOutlined, SearchOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { DataNode } from 'antd/es/tree'
import { stockPoolApi } from '../services/api'

const { Title } = Typography
const { TabPane } = Tabs

interface PoolItem {
  id: string
  code: string
  name: string
  sector?: string
  industry?: string
  concept?: string
  market?: string
  added_at: string
  source: string
}

interface SectorNode {
  key: string
  title: string
  children?: SectorNode[]
  type?: 'sector' | 'industry' | 'concept' | 'market'
  code?: string
}

export default function StockPool() {
  const [activeTab, setActiveTab] = useState('all')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)

  const [allStocks, setAllStocks] = useState<PoolItem[]>([])
  const [allTotal, setAllTotal] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [transferOptions, setTransferOptions] = useState<{ key: string; title: string; description: string }[]>([])
  const [transferLoading, setTransferLoading] = useState(false)

  const [pools, setPools] = useState<{ id: number; name: string; stock_count: number }[]>([])
  const [selectedPool, setSelectedPool] = useState<number>(1)
  const [poolStocks, setPoolStocks] = useState<PoolItem[]>([])
  const [poolTotal, setPoolTotal] = useState(0)
  const [poolPage, setPoolPage] = useState(1)
  const [poolPageSize, setPoolPageSize] = useState(50)
  const [sectors, setSectors] = useState<SectorNode[]>([])
  const [selectedSector, setSelectedSector] = useState<string | null>(null)

  const [keyword, setKeyword] = useState('')
  const [createVisible, setCreateVisible] = useState(false)
  const [newPoolName, setNewPoolName] = useState('')
  const [transferVisible, setTransferVisible] = useState(false)
  const [transferTargetKeys, setTransferTargetKeys] = useState<React.Key[]>([])
  const [form] = Form.useForm()
  const syncTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [syncStatus, setSyncStatus] = useState<any>(null)

  const loadAllStocks = async (page = currentPage, size = pageSize) => {
    setLoading(true)
    try {
      const params: any = { page, page_size: size }
      if (selectedSector) {
        const [, type, code] = selectedSector.split(':')
        if (type === 'industry') params.industry_code = code
        if (type === 'concept') params.concept_code = code
      }
      if (keyword.trim()) {
        params.keyword = keyword.trim()
      }
      const res = await stockPoolApi.list(params)
      setAllTotal(res.data.total || 0)
      setAllStocks((res.data.items || []).map((s: any) => ({
        id: s.code,
        code: s.code,
        name: s.name,
        market: s.market,
        industries: s.industries || [],
        concepts: s.concepts || [],
        added_at: s.updated_at,
        source: 'db'
      })))
    } catch (error) {
      console.error('加载股票失败:', error)
      message.error('加载股票失败')
    } finally {
      setLoading(false)
    }
  }

  const loadPools = async () => {
    try {
      const res = await stockPoolApi.pools()
      const list = (res.data || []).map((p: any) => ({
        id: p.id,
        name: p.name,
        stock_count: p.stock_count || 0,
      }))
      if (!list.length) {
        setPools([{ id: 1, name: 'default', stock_count: 0 }])
        setSelectedPool(1)
      } else {
        setPools(list)
        if (!list.find((p: any) => p.id === selectedPool)) {
          setSelectedPool(list[0].id)
        }
      }
    } catch (error) {
      console.error('加载股票池失败:', error)
      setPools([{ id: 1, name: 'default', stock_count: 0 }])
      setSelectedPool(1)
    }
  }

  const loadPoolStocks = async (page = poolPage, size = poolPageSize) => {
    setLoading(true)
    try {
      const res = await stockPoolApi.poolStocks(selectedPool, { page, page_size: size })
      setPoolTotal((res.data || []).length) // 后端池内接口当前返回数组，暂时用长度
      setPoolStocks((res.data || []).map((it: any) => ({
        id: it.stock_code,
        code: it.stock_code,
        name: it.stock?.name || it.stock_code,
        market: it.stock?.market,
        industries: it.stock?.industries || [],
        concepts: it.stock?.concepts || [],
        added_at: it.added_at,
        source: 'pool'
      })))
    } catch (error) {
      console.error('加载股票池股票失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadSectors = async () => {
    try {
      const [industryRes, conceptRes] = await Promise.all([
        stockPoolApi.industries(),
        stockPoolApi.concepts()
      ])
      const industries = (industryRes.data || []).slice(0, 100).map((s: any) => ({ key: `industry:${s.code || s.name}`, title: s.name, type: 'industry' as const, code: s.code || s.name }))
      const concepts = (conceptRes.data || []).slice(0, 100).map((s: any) => ({ key: `concept:${s.code || s.name}`, title: s.name, type: 'concept' as const, code: s.code || s.name }))
      setSectors([
        { key: 'market', title: '全市场', type: 'market', code: 'all' },
        { key: 'sector', title: '板块', type: 'sector', children: [] },
        { key: 'industry', title: '行业', type: 'industry', children: industries },
        { key: 'concept', title: '概念', type: 'concept', children: concepts }
      ])
    } catch (error) {
      console.error('加载板块分类失败:', error)
    }
  }

  const syncStocks = async () => {
    setSyncing(true)
    try {
      await stockPoolApi.sync({ market: 'all' })
      message.success('股票池同步任务已触发')
      if (syncTimerRef.current) clearInterval(syncTimerRef.current)
      syncTimerRef.current = setInterval(async () => {
        try {
          const res = await stockPoolApi.syncStatus()
          const data = res.data
          setSyncStatus(data)
          if (data.status === 'done' || data.status === 'failed') {
            if (syncTimerRef.current) clearInterval(syncTimerRef.current)
            setSyncing(false)
            loadAllStocks()
            loadSectors()
            if (data.status === 'done') {
              message.success('同步完成')
            } else {
              message.error(`同步失败: ${data.error || '未知错误'}`)
            }
          }
        } catch (error) {
          console.error('查询同步状态失败:', error)
        }
      }, 2000)
    } catch (error) {
      message.error('同步失败')
      setSyncing(false)
    }
  }

  useEffect(() => {
    return () => {
      if (syncTimerRef.current) clearInterval(syncTimerRef.current)
    }
  }, [])

  const handleSearch = async () => {
    setCurrentPage(1)
    loadAllStocks(1, pageSize)
  }

  const addToPool = async (codes: string[]) => {
    if (!codes.length) return
    try {
      for (const code of codes) {
        await stockPoolApi.addToPool(selectedPool, { codes: [code] })
      }
      message.success(`已添加 ${codes.length} 只股票到 ${selectedPool}`)
      loadPoolStocks()
    } catch (error) {
      message.error('添加失败')
    }
  }

  const removeFromPool = async (code: string) => {
    try {
      await stockPoolApi.removeFromPool(selectedPool, code)
      loadPoolStocks()
    } catch (error) {
      message.error('移除失败')
    }
  }

  const createPool = async () => {
    if (!newPoolName.trim()) return
    try {
      await stockPoolApi.createPool({ name: newPoolName })
      setCreateVisible(false)
      setNewPoolName('')
      loadPools()
    } catch (error) {
      message.error('创建失败')
    }
  }

  const openTransfer = async () => {
    setTransferTargetKeys([])
    form.setFieldsValue({ codes: [] })
    setTransferVisible(true)
    setTransferLoading(true)
    try {
      const res = await stockPoolApi.list({ page_size: 3000 })
      setTransferOptions((res.data.items || []).map((s: any) => ({
        key: s.code,
        title: `${s.name}(${s.code})`,
        description: `${(s.industries || []).slice(0, 2).join(' ')} ${(s.concepts || []).slice(0, 2).join(' ')}`.trim()
      })))
    } catch (error) {
      message.error('加载可选股票失败')
    } finally {
      setTransferLoading(false)
    }
  }

  const handleTransferOk = () => {
    addToPool(transferTargetKeys as string[])
    setTransferVisible(false)
  }

  useEffect(() => {
    loadPools()
    loadSectors()
    loadAllStocks(1, pageSize)
  }, [])

  useEffect(() => {
    loadPoolStocks(1, poolPageSize)
  }, [selectedPool])

  useEffect(() => {
    setCurrentPage(1)
    loadAllStocks(1, pageSize)
  }, [selectedSector])

  const columns: ColumnsType<PoolItem> = [
    { title: '代码', dataIndex: 'code', width: 100 },
    { title: '名称', dataIndex: 'name', width: 120 },
    {
      title: '行业',
      dataIndex: 'industries',
      render: (v: string[]) => v?.length ? v.slice(0, 3).map((name: string) => <Tag key={name} color="blue">{name}</Tag>) : '-'
    },
    {
      title: '概念',
      dataIndex: 'concepts',
      render: (v: string[]) => v?.length ? v.slice(0, 3).map((name: string) => <Tag key={name} color="green">{name}</Tag>) : '-'
    },
    { title: '市场', dataIndex: 'market', width: 80 },
    { title: '来源', dataIndex: 'source', width: 100 },
    {
      title: '操作',
      fixed: 'right',
      width: 140,
      render: (_, r) => (
        <Space>
          <Button size="small" onClick={() => addToPool([r.code])}>加入池</Button>
          {activeTab === 'pool' && (
            <Popconfirm title="确认移除？" onConfirm={() => removeFromPool(r.code)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      )
    }
  ]

  const treeData: DataNode[] = sectors.map((s) => ({
    key: s.key,
    title: s.title,
    icon: s.type === 'market' ? <DatabaseOutlined /> : <ApartmentOutlined />,
    children: s.children?.map((c) => ({
      key: c.key,
      title: c.title,
      icon: <FolderOutlined />
    }))
  }))

  const onTreeSelect = (keys: any[]) => {
    if (!keys.length) {
      setSelectedSector(null)
      return
    }
    const key = keys[0] as string
    if (key === 'market') {
      setSelectedSector(null)
    } else {
      setSelectedSector(key)
    }
  }

  const selectedPoolName = pools.find((p) => p.id === selectedPool)?.name || selectedPool

  return (
    <div>
      <Title level={4}><DatabaseOutlined /> 股票池管理</Title>

      <Row gutter={16}>
        <Col span={5}>
          <Card title="分类导航" size="small">
            <Tree
              treeData={treeData}
              defaultExpandedKeys={['sector', 'industry', 'concept']}
              onSelect={onTreeSelect}
              showIcon
            />
          </Card>
        </Col>

        <Col span={19}>
          <Card
            title={
              <Space>
                <Select value={selectedPool} onChange={setSelectedPool} style={{ width: 160 }} options={pools.map((p) => ({ label: p.name, value: p.id }))} />
                <Button icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>新建池</Button>
                <Button icon={<SyncOutlined />} loading={syncing} onClick={syncStocks}>同步全市场</Button>
                {syncStatus?.status === 'running' && syncStatus.steps && syncStatus.steps.length > 0 && (
                  <span style={{ marginLeft: 12, color: '#1890ff' }}>
                    同步中: {syncStatus.steps[syncStatus.steps.length - 1].message || syncStatus.status}
                  </span>
                )}
                {syncStatus?.status === 'done' && (
                  <span style={{ marginLeft: 12, color: '#52c41a' }}>同步完成</span>
                )}
                {syncStatus?.status === 'failed' && (
                  <span style={{ marginLeft: 12, color: '#f5222d' }}>同步失败</span>
                )}
                <Button onClick={openTransfer}>批量加入</Button>
              </Space>
            }
            extra={
              <Space>
                <Input.Search
                  placeholder="搜索代码/名称"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  onSearch={handleSearch}
                  style={{ width: 200 }}
                  enterButton={<SearchOutlined />}
                />
              </Space>
            }
          >
            <Tabs activeKey={activeTab} onChange={setActiveTab}>
              <TabPane tab={<span><DatabaseOutlined /> 全市场 ({allTotal})</span>} key="all">
                <Spin spinning={loading}>
                  <Table
                    columns={columns.filter((c) => c.title !== '来源')}
                    dataSource={allStocks}
                    rowKey="code"
                    size="small"
                    pagination={{
                      current: currentPage,
                      pageSize,
                      total: allTotal,
                      showSizeChanger: true,
                      onChange: (page, size) => {
                        setCurrentPage(page)
                        if (size) setPageSize(size)
                        loadAllStocks(page, size || pageSize)
                      }
                    }}
                    scroll={{ x: 900 }}
                  />
                </Spin>
              </TabPane>

              <TabPane tab={<span><FolderOutlined /> {selectedPoolName} ({poolTotal})</span>} key="pool">
                <Spin spinning={loading}>
                  <Table
                    columns={columns}
                    dataSource={poolStocks}
                    rowKey="code"
                    size="small"
                    pagination={{
                      current: poolPage,
                      pageSize: poolPageSize,
                      total: poolTotal,
                      showSizeChanger: true,
                      onChange: (page, size) => {
                        setPoolPage(page)
                        if (size) setPoolPageSize(size)
                        loadPoolStocks(page, size || poolPageSize)
                      }
                    }}
                    scroll={{ x: 900 }}
                  />
                </Spin>
              </TabPane>
            </Tabs>
          </Card>
        </Col>
      </Row>

      <Modal
        title="新建股票池"
        open={createVisible}
        onOk={createPool}
        onCancel={() => { setCreateVisible(false); setNewPoolName('') }}
      >
        <Input
          placeholder="请输入股票池名称"
          value={newPoolName}
          onChange={(e) => setNewPoolName(e.target.value)}
          onPressEnter={createPool}
        />
      </Modal>

      <Modal
        title="批量加入股票池"
        open={transferVisible}
        onOk={handleTransferOk}
        onCancel={() => setTransferVisible(false)}
        width={700}
      >
        <Transfer
          dataSource={transferOptions}
          titles={['全市场股票', `加入 ${selectedPoolName}`]}
          targetKeys={transferTargetKeys}
          onChange={(nextKeys) => setTransferTargetKeys(nextKeys)}
          render={(item) => item.title}
          listStyle={{ width: 300, height: 400 }}
          showSearch
          disabled={transferLoading}
          filterOption={(inputValue, item: any) => item.title?.toLowerCase().includes(inputValue.toLowerCase()) || false}
        />
      </Modal>
    </div>
  )
}
