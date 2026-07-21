import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  BuildOutlined,
  ExperimentOutlined,
  ReadOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'

import Dashboard from './pages/Dashboard'
import Strategy from './pages/Strategy'
import Backtest from './pages/Backtest'
import News from './pages/News'
import Settings from './pages/Settings'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '实时行情' },
  { key: '/strategy', icon: <BuildOutlined />, label: '策略管理' },
  { key: '/backtest', icon: <ExperimentOutlined />, label: '回测分析' },
  { key: '/news', icon: <ReadOutlined />, label: '新闻分析' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
]

function App() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px', display: 'flex', alignItems: 'center' }}>
        <div style={{ color: '#fff', fontSize: 20, fontWeight: 'bold', marginRight: 40 }}>
          🤖 AI量化交易系统
        </div>
        <div style={{ color: '#fff', fontSize: 14, opacity: 0.8 }}>
          平安证券 | 10万资金
        </div>
      </Header>
      <Layout>
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ height: '100%', borderRight: 0 }}
          />
        </Sider>
        <Layout style={{ padding: '0 24px 24px' }}>
          <Content
            style={{
              padding: 24,
              margin: 0,
              minHeight: 280,
              background: '#fff',
              borderRadius: 8,
            }}
          >
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/strategy" element={<Strategy />} />
              <Route path="/backtest" element={<Backtest />} />
              <Route path="/news" element={<News />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

export default App
