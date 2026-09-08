import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import Login from './pages/Login'
import Overview from './pages/Overview'
import AirfarePriceIndex from './pages/AirfarePriceIndex'
import RouteAnalysis from './pages/RouteAnalysis'
import SectorHeatmap from './pages/SectorHeatmap'
import LeadTimeAnalysis from './pages/LeadTimeAnalysis'
import AirlineAnalysis from './pages/AirlineAnalysis'
import DataExplorer from './pages/DataExplorer'
import DataQuality from './pages/DataQuality'
import ScrapingMonitor from './pages/ScrapingMonitor'
import Backtesting from './pages/Backtesting'
import Methodology from './pages/Methodology'
import ApiDocs from './pages/ApiDocs'
import Admin from './pages/Admin'

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Overview />} />
          <Route path="index" element={<AirfarePriceIndex />} />
          <Route path="routes" element={<RouteAnalysis />} />
          <Route path="heatmap" element={<SectorHeatmap />} />
          <Route path="lead-time" element={<LeadTimeAnalysis />} />
          <Route path="airlines" element={<AirlineAnalysis />} />
          <Route path="explorer" element={<DataExplorer />} />
          <Route path="quality" element={<DataQuality />} />
          <Route path="scraping" element={<ScrapingMonitor />} />
          <Route path="backtesting" element={<Backtesting />} />
          <Route path="methodology" element={<Methodology />} />
          <Route path="api-docs" element={<ApiDocs />} />
          <Route path="admin" element={<Admin />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
