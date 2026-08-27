import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    qualities: [72],
    formats: ["image/avif", "image/webp"],
  },
};

export default nextConfig;
