/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  // Add this images config for static export
  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;
