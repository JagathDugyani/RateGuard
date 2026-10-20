# Rate Limiting

Token Bucket tracks refillable tokens per client. Leaky Bucket tracks queued requests and drains them at a controlled rate. The manager can switch algorithms at runtime.