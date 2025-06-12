// src/pages/EditStrategyPage.tsx
import React, { useState, useEffect } from 'react';
import StrategyEditor from '../components/StrategyEditor';
import { Container, Typography, CircularProgress, Alert } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';

interface StrategyData { // Ensure this matches the structure in StrategyEditor
  strategy_id?: string;
  name: string;
  author: string;
  description: string;
  content_type: 'plaintext' | 'markdown';
  content: string;
  target_instrument?: string;
  target_timeframe?: string;
}

const EditStrategyPage: React.FC = () => {
  const { strategyId } = useParams<{ strategyId: string }>();
  const navigate = useNavigate();
  const [initialData, setInitialData] = useState<StrategyData | undefined>(undefined);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (strategyId) {
      const fetchStrategy = async () => {
        setLoading(true);
        setError(null);
        try {
          const response = await fetch(`/api/strategies/${strategyId}`);
          if (!response.ok) {
            throw new Error(`Failed to fetch strategy: ${response.status}`);
          }
          const data: StrategyData = await response.json();
          setInitialData(data);
        } catch (err: any) {
          setError(err.message);
        } finally {
          setLoading(false);
        }
      };
      fetchStrategy();
    } else {
      setError("No strategy ID provided.");
      setLoading(false);
    }
  }, [strategyId]);

  if (loading) {
    return <Container sx={{display: 'flex', justifyContent: 'center', mt: 5}}><CircularProgress /></Container>;
  }

  if (error) {
     return <Container sx={{mt:2}}><Alert severity="error">Error loading strategy: {error}</Alert></Container>;
  }

  if (!initialData) {
     return <Container sx={{mt:2}}><Alert severity="warning">Strategy data not found.</Alert></Container>;
  }

  return (
    <Container maxWidth="md">
      <StrategyEditor
        strategyId={strategyId}
        initialData={initialData}
        onSaveSuccess={() => {
          navigate('/strategies'); // Navigate to dashboard after successful edit
        }}
      />
    </Container>
  );
};

export default EditStrategyPage;
