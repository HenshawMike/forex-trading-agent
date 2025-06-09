import React, { useState } from 'react';
import './Settings.css';

const Settings: React.FC = () => {
  const [settings, setSettings] = useState({
    apiKey: '',
    riskLevel: 'medium',
    tradingPair: 'EUR/USD',
    stopLoss: '50',
    takeProfit: '100'
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setSettings(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Settings saved:', settings);
    // TODO: Implement settings save functionality
  };

  return (
    <div className="settings">
      <h1>Trading Settings</h1>
      <form className="settings-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="apiKey">API Key</label>
          <input
            type="password"
            id="apiKey"
            name="apiKey"
            value={settings.apiKey}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label htmlFor="riskLevel">Risk Level</label>
          <select
            id="riskLevel"
            name="riskLevel"
            value={settings.riskLevel}
            onChange={handleChange}
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="tradingPair">Trading Pair</label>
          <select
            id="tradingPair"
            name="tradingPair"
            value={settings.tradingPair}
            onChange={handleChange}
          >
            <option value="EUR/USD">EUR/USD</option>
            <option value="GBP/USD">GBP/USD</option>
            <option value="USD/JPY">USD/JPY</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="stopLoss">Stop Loss (pips)</label>
          <input
            type="number"
            id="stopLoss"
            name="stopLoss"
            value={settings.stopLoss}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label htmlFor="takeProfit">Take Profit (pips)</label>
          <input
            type="number"
            id="takeProfit"
            name="takeProfit"
            value={settings.takeProfit}
            onChange={handleChange}
          />
        </div>

        <button type="submit" className="save-button">Save Settings</button>
      </form>
    </div>
  );
};

export default Settings;
