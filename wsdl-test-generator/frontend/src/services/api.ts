// frontend/src/services/api.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api', // Adjust if backend URL is different
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- TypeScript Interfaces ---
export interface GenerationResponse {
  generationId: string;
  xmlContents?: string[];
  errorMessage?: string;
}

export interface FeedbackResponse {
  xmlContents?: string[];
  errorMessage?: string;
}

// --- API Functions ---
export const generateTests = async (
  wsdlFile: File,
  testOptions: string[]
): Promise<GenerationResponse> => {
  const formData = new FormData();
  formData.append('wsdl_file', wsdlFile);
  testOptions.forEach(option => formData.append('test_options', option));

  const response = await apiClient.post<GenerationResponse>('/generations', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const submitFeedback = async (
  generationId: string,
  feedback: string
): Promise<FeedbackResponse> => {
  const response = await apiClient.post<FeedbackResponse>(
    `/generations/${generationId}/feedback`,
    { feedback }
  );
  return response.data;
};
