// src/pages/CreateStrategyPage.tsx
import React from 'react';
import StrategyEditor from '../components/StrategyEditor';
import { Container, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';

const CreateStrategyPage: React.FC = () => {
  const navigate = useNavigate();
  return (
    <Container maxWidth="md">
      {/* Typography for page title removed as StrategyEditor has its own title */}
      <StrategyEditor
        onSaveSuccess={() => {
          // Later, navigate to the main strategies list page or the edited strategy's page
          // For now, let's assume a general strategies list page
          navigate('/strategies');
        }}
      />
    </Container>
  );
};

export default CreateStrategyPage;
