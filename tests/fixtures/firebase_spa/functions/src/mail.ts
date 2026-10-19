
import * as nodemailer from 'nodemailer';
import { defineSecret } from 'firebase-functions/params';
import { SecretManagerServiceClient } from '@google-cloud/secret-manager';
export const openaiKey = defineSecret('OPENAI_KEY');
export async function send() {
  const client = new SecretManagerServiceClient();
  const transporter = nodemailer.createTransport({ host: 'smtp.gmail.com', port: 465 });
  await transporter.sendMail({ to: 'parent@example.com', subject: '안내' });
}
import rateLimit from 'express-rate-limit';
export const limiter = rateLimit({ windowMs: 60000, max: 20 });
export function ip(req: any) { return req.ip || req.headers['x-forwarded-for']; }
