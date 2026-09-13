import apiClient from "./client";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  display_name: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  display_name: string;
  role: string;
}

export const loginApi = (data: LoginRequest) =>
  apiClient.post<TokenResponse>("/auth/login", data);

export const registerApi = (data: RegisterRequest) =>
  apiClient.post<TokenResponse>("/auth/register", data);

export const getMeApi = () =>
  apiClient.get<UserResponse>("/auth/me");
