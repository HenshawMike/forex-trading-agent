import React, { useState } from 'react';
import './TradingView.css';

const TradingView = () => {
  const [selectedPair, setSelectedPair] = useState('EUR/USD');
  const [amount, setAmount] = useState('');

  const handleTrade = (action: 'buy' | 'sell') => {
    // Implement trading logic here
    console.log(`${action} ${amount} ${selectedPair}`);
  };

  return (
    <div className="trading-view">
      <div className="trading-controls">
        <select 
          value={selectedPair} 
          onChange={(e) => setSelectedPair(e.target.value)}
        >
          <option value="EUR/USD">EUR/USD</option>
          <option value="GBP/USD">GBP/USD</option>
          <option value="USD/JPY">USD/JPY</option>
        </select>
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Amount"
        />
        <div className="action-buttons">
          <button onClick={() => handleTrade('buy')} className="buy-btn">
            Buy
          </button>
          <button onClick={() => handleTrade('sell')} className="sell-btn">
            Sell
          </button>
        </div>
      </div>
    </div>
  );
};

export default TradingView;
