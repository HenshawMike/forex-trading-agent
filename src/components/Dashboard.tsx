import React from 'react';
import './Dashboard.css';

const Dashboard = () => {
  return (
    <div className="dashboard">
      <div className="stats-container">
        <div className="stat-card">
          <h3>Current Balance</h3>
          <p>$10,000.00</p>
        </div>
        <div className="stat-card">
          <h3>Open Positions</h3>
          <p>5</p>
        </div>
        <div className="stat-card">
          <h3>Daily P/L</h3>
          <p>+$250.00</p>
        </div>
      </div>
      <div className="chart-container">
        {/* Add your trading chart component here */}
      </div>
    </div>
  );
};

export default Dashboard;
