'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';

// Dynamically import Plotly to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface PlotlyPlotProps {
  spec: {
    data?: any[];
    layout?: any;
    [key: string]: any;
  };
  plotType?: string;
}

export default function PlotlyPlot({ spec, plotType }: PlotlyPlotProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  // Prevent body scrolling when modal is open
  useEffect(() => {
    if (isModalOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isModalOpen]);

  const handleZoomClick = () => {
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      handleCloseModal();
    }
  };

  if (!spec || !isClient) {
    return null;
  }

  // Extract data and layout from spec
  const plotData = spec.data || [];
  const plotLayout = spec.layout || {};

  // Default responsive layout for inline plot
  const inlineLayout = {
    ...plotLayout,
    autosize: true,
    width: undefined, // Let it be responsive
    height: 500,
    margin: {
      ...plotLayout.margin,
      l: 80,
      r: 50,
      t: 80,
      b: 80,
    },
  };

  // Larger layout for modal
  const modalLayout = {
    ...plotLayout,
    autosize: true,
    width: undefined,
    height: isClient ? Math.max(600, window.innerHeight * 0.8) : 600,
    margin: {
      ...plotLayout.margin,
      l: 100,
      r: 80,
      t: 100,
      b: 100,
    },
  };

  const config = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    responsive: true,
  };

  return (
    <>
      <div className="w-full my-4 relative">
        <div className="w-full min-h-[500px]">
          <Plot
            data={plotData}
            layout={inlineLayout}
            config={config}
            style={{ width: '100%', height: '100%' }}
            useResizeHandler={true}
          />
        </div>
        {/* Zoom button */}
        <button
          onClick={handleZoomClick}
          className="absolute top-2 right-2 z-10 rounded-md bg-background/80 hover:bg-background border border-border/50 px-2 py-1.5 text-xs font-medium shadow-sm transition-colors hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          aria-label="Zoom plot"
          title="Zoom plot"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"
            />
          </svg>
        </button>
      </div>

      {/* Modal overlay */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm transition-opacity"
          onClick={handleBackdropClick}
        >
          <div className="relative w-[90vw] h-[90vh] max-w-7xl max-h-[90vh] bg-background rounded-lg shadow-xl border border-border/50 overflow-hidden">
            {/* Close button */}
            <button
              onClick={handleCloseModal}
              className="absolute top-4 right-4 z-20 rounded-md bg-background/90 hover:bg-background border border-border/50 p-2 shadow-sm transition-colors hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              aria-label="Close modal"
              title="Close"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
            {/* Plot container in modal */}
            <div className="w-full h-full p-8 overflow-auto">
              <div className="w-full h-full min-h-[600px]">
                <Plot
                  data={plotData}
                  layout={modalLayout}
                  config={config}
                  style={{ width: '100%', height: '100%' }}
                  useResizeHandler={true}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
