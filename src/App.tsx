import React from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import TradingView from './components/TradingView';
import Settings from './components/Settings';
import CreateStrategyPage from './pages/CreateStrategyPage';
import StrategyDashboardPage from './pages/StrategyDashboardPage'; // Added import
import EditStrategyPage from './pages/EditStrategyPage'; // Added import
import './App.css';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { theme } from './theme';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <div className="app">
          <Navbar />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/trading" element={<TradingView />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/strategies" element={<StrategyDashboardPage />} /> {/* Added route */}
              <Route path="/strategies/new" element={<CreateStrategyPage />} />
              <Route path="/strategies/edit/:strategyId" element={<EditStrategyPage />} /> {/* Added route */}
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
