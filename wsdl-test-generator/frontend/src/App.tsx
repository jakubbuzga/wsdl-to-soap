import React, { useState } from 'react';
import { generateTests, submitFeedback } from './services/api';
import {
  Container,
  Typography,
  Box,
  Button,
  TextField,
  CircularProgress,
  Alert,
  Checkbox,
  FormGroup,
  FormControlLabel,
  Paper,
  Grid,
} from '@mui/material';
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import xml from 'react-syntax-highlighter/dist/esm/languages/hljs/xml';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';

SyntaxHighlighter.registerLanguage('xml', xml);

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [xmlContent, setXmlContent] = useState('');
  const [generationId, setGenerationId] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [testOptions, setTestOptions] = useState<string[]>([]);
  const [feedbackText, setFeedbackText] = useState('');

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleOptionChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value, checked } = event.target;
    if (checked) {
      setTestOptions((prev) => [...prev, value]);
    } else {
      setTestOptions((prev) => prev.filter((option) => option !== value));
    }
  };

  const handleGenerate = async () => {
    if (!selectedFile) {
      setErrorMessage('Please select a WSDL file.');
      return;
    }
    setIsLoading(true);
    setErrorMessage('');
    setXmlContent('');
    try {
      const response = await generateTests(selectedFile, testOptions);
      if (response.errorMessage) {
        setErrorMessage(response.errorMessage);
      } else {
        setXmlContent(response.xmlContent || '');
        setGenerationId(response.generationId);
      }
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || 'An unknown error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedback = async () => {
    if (!feedbackText || !generationId) return;
    setIsLoading(true);
    setErrorMessage('');
    try {
      const response = await submitFeedback(generationId, feedbackText);
      if (response.errorMessage) {
        setErrorMessage(response.errorMessage);
      } else {
        setXmlContent(response.xmlContent || '');
        setFeedbackText('');
      }
    } catch (error: any) {
      setErrorMessage(error.response?.data?.detail || 'An unknown error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = () => {
    if (!xmlContent) return;
    const blob = new Blob([xmlContent], { type: 'text/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'test_cases.xml';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          WSDL-to-SOAP Test Generator
        </Typography>

        <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
          <Typography variant="h6">1. Upload WSDL</Typography>
          <input
            type="file"
            accept=".wsdl"
            onChange={handleFileChange}
            style={{ marginTop: '10px', marginBottom: '20px' }}
          />

          <Typography variant="h6">2. Select Test Case Types</Typography>
          <FormGroup row>
            <FormControlLabel control={<Checkbox onChange={handleOptionChange} value="happy_path" />} label="Happy Path" />
            <FormControlLabel control={<Checkbox onChange={handleOptionChange} value="negative_cases" />} label="Negative Cases" />
            <FormControlLabel control={<Checkbox onChange={handleOptionChange} value="edge_cases" />} label="Edge Cases" />
          </FormGroup>

          <Button
            variant="contained"
            onClick={handleGenerate}
            disabled={isLoading || !selectedFile}
            sx={{ mt: 2 }}
          >
            Generate Tests
          </Button>
        </Paper>

        {isLoading && <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}><CircularProgress /></Box>}
        {errorMessage && <Alert severity="error" sx={{ my: 2 }}>{errorMessage}</Alert>}

        {xmlContent && (
          <Paper elevation={3} sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom>Generated SOAP Tests</Typography>
            <Button onClick={handleDownload} variant="outlined" sx={{ mb: 2 }}>Download XML</Button>
            <SyntaxHighlighter language="xml" style={docco} customStyle={{ maxHeight: '500px', overflowY: 'auto' }}>
              {xmlContent}
            </SyntaxHighlighter>

            <Box sx={{ mt: 4 }}>
              <Typography variant="h6">3. Provide Feedback for Regeneration</Typography>
              <TextField
                fullWidth
                multiline
                rows={4}
                variant="outlined"
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
                placeholder="e.g., 'The negative test is missing. Please add a test where 'a' is zero.'"
                sx={{ my: 2 }}
              />
              <Button
                variant="contained"
                color="secondary"
                onClick={handleFeedback}
                disabled={isLoading || !feedbackText}
              >
                Regenerate with Feedback
              </Button>
            </Box>
          </Paper>
        )}
      </Box>
    </Container>
  );
}

export default App;
