'use client';

import { useEffect, useRef, useState } from 'react';
import embed from 'vega-embed';

interface VegaPlotProps {
  spec: Record<string, any>;
  plotType?: string;
}

export default function VegaPlot({ spec, plotType }: VegaPlotProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const modalContainerRef = useRef<HTMLDivElement>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    if (!containerRef.current || !spec) return;

    // Clear any existing content
    containerRef.current.innerHTML = '';

    // Embed the Vega-Lite specification
    embed(containerRef.current, spec, {
      actions: {
        export: true,
        source: false,
        compiled: false,
        editor: false,
      },
      theme: 'quartz',
    }).catch((error) => {
      console.error('Error rendering Vega plot:', error);
      if (containerRef.current) {
        containerRef.current.innerHTML = '<p className="text-sm text-muted-foreground">Error rendering plot</p>';
      }
    });
  }, [spec]);

  // Render plot in modal when opened
  useEffect(() => {
    if (!isModalOpen || !modalContainerRef.current || !spec) return;

    // Wait a tick to ensure the modal container is fully rendered and measured
    const renderPlot = () => {
      if (!modalContainerRef.current) return;

      // Clear any existing content
      modalContainerRef.current.innerHTML = '';

      // Get container dimensions - use a reasonable default if not yet measured
      const containerWidth = modalContainerRef.current.offsetWidth || window.innerWidth * 0.8;
      const containerHeight = modalContainerRef.current.offsetHeight || window.innerHeight * 0.8;
      
      // Create a modified spec with larger dimensions
      const enlargedSpec = JSON.parse(JSON.stringify(spec)); // Deep copy to avoid mutating original
      
      // Calculate enlarged dimensions - use at least 2.5x the original or container size
      const originalWidth = spec.width || 400;
      const originalHeight = spec.height || 300;
      
      // Scale up significantly - use the larger of 2.5x original or container size minus padding
      enlargedSpec.width = Math.max(originalWidth * 2.5, containerWidth - 100);
      enlargedSpec.height = Math.max(originalHeight * 2.5, containerHeight - 100);

      // Embed the enlarged Vega-Lite specification in modal
      embed(modalContainerRef.current, enlargedSpec, {
        actions: {
          export: true,
          source: false,
          compiled: false,
          editor: false,
        },
        theme: 'quartz',
      }).catch((error) => {
        console.error('Error rendering Vega plot in modal:', error);
        if (modalContainerRef.current) {
          modalContainerRef.current.innerHTML = '<p className="text-sm text-muted-foreground">Error rendering plot</p>';
        }
      });
    };

    // Use requestAnimationFrame to ensure DOM is ready
    requestAnimationFrame(() => {
      setTimeout(renderPlot, 0);
    });
  }, [isModalOpen, spec]);

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

  if (!spec) {
    return null;
  }

  return (
    <>
      <div className="w-full my-4 relative">
        <div ref={containerRef} className="w-full" />
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
              <div ref={modalContainerRef} className="w-full h-full" />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

