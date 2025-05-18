"use client";

import { useState, useEffect } from "react";
import { useCopilotAction, useCoAgent } from "@copilotkit/react-core";
import { Markdown } from "@copilotkit/react-ui";
import dynamic from 'next/dynamic';

// Dynamic import for the CopilotSidebar to avoid hydration issues
const CopilotSidebar = dynamic(
  () => import('@copilotkit/react-ui').then((mod) => mod.CopilotSidebar),
  { ssr: false } // Disable server-side rendering for this component
);

// DevRelAgentState interface matching our Python state
interface DevRelAgentState {
  repo_url: string;
  start_date: string;
  topics: Array<{
    title: string;
    description: string;
    source_type: string;
    source_id: string;
    content_types: string[];
  }>;
  selected_topic: any;
  content_drafts: {
    blog_post: string;
    code_example: string;
    social_media: string;
  };
  content_record: {
    channel: string;
    title: string;
    summary: string;
    content: string;
    type: string;
  };
  status?: string;
  error?: string;
  copilotkit?: {
    actions?: any[];
    metadata?: Record<string, any>;
  };
  messages?: any[];
}

export default function Home() {
  // Add a state to track client-side rendering
  const [isClient, setIsClient] = useState(false);
  
  // Set isClient to true when component mounts on the client
  useEffect(() => {
    setIsClient(true);
  }, []);
  
  // Only render the sidebar component on the client
  if (!isClient) {
    return <div className="min-h-screen bg-gray-50 flex items-center justify-center">Loading...</div>;
  }
  
  return (
    <div className="min-h-screen bg-gray-50">
      <CopilotSidebar
        defaultOpen={true}
        labels={{
          title: "DevRel Publisher",
          initial: "I'm your DevRel content publishing assistant. I can help you generate content based on your GitHub repository changes.",
        }}
      >
        <DevRelPublisher />
      </CopilotSidebar>
    </div>
  );
}

function DevRelPublisher() {
  const { state, setState } = useCoAgent<DevRelAgentState>({
    name: "devrel_publisher",
    initialState: {
      repo_url: "",
      start_date: "",
      topics: [],
      selected_topic: null,
      content_drafts: {
        blog_post: "",
        code_example: "",
        social_media: ""
      },
      content_record: {
        channel: "",
        title: "",
        summary: "",
        content: "",
        type: ""
      }
    }
  });
  
  const [activeStep, setActiveStep] = useState(1);

  // GitHub Repository Input Action
  useCopilotAction({
    name: "set_github_repo",
    description: "Set the GitHub repository URL for analysis",
    parameters: [
      { name: "repo_url", type: "string", description: "GitHub repository URL", required: true }
    ],
    renderAndWaitForResponse: ({ args, respond, status }) => (
      <div className="p-4 border rounded bg-white shadow-sm">
        <h2 className="text-lg font-bold mb-2">Enter GitHub Repository</h2>
        <input
          type="text"
          placeholder="https://github.com/owner/repo"
          className="w-full p-2 border rounded mb-4"
          value={state?.repo_url || ""}
          onChange={(e) => setState && setState({ ...state, repo_url: e.target.value })}
        />
        <div className="flex gap-2">
          <button
            onClick={() => respond && respond(state?.repo_url)}
            disabled={status !== "executing"}
            className="bg-blue-500 text-white px-4 py-2 rounded disabled:bg-blue-300"
          >
            Submit
          </button>
        </div>
      </div>
    )
  });

  // Date Range Selector Action
  useCopilotAction({
    name: "set_date_range",
    description: "Set the start date for repository analysis",
    parameters: [
      { name: "start_date", type: "string", description: "Start date in YYYY-MM-DD format", required: true }
    ],
    renderAndWaitForResponse: ({ args, respond, status }) => (
      <div className="p-4 border rounded bg-white shadow-sm">
        <h2 className="text-lg font-bold mb-2">Select Analysis Start Date</h2>
        <p className="text-sm text-gray-500 mb-2">
          We'll analyze repository changes after this date
        </p>
        <input
          type="date"
          className="w-full p-2 border rounded mb-4"
          value={state?.start_date || ""}
          onChange={(e) => setState && setState({ ...state, start_date: e.target.value })}
        />
        <div className="flex gap-2">
          <button
            onClick={() => respond && respond(state?.start_date)}
            disabled={status !== "executing"}
            className="bg-blue-500 text-white px-4 py-2 rounded disabled:bg-blue-300"
          >
            Submit
          </button>
        </div>
      </div>
    )
  });

  // Topic Selection Action
  useCopilotAction({
    name: "select_topic",
    description: "Select a topic for content generation",
    parameters: [
      { name: "topic_index", type: "number", description: "Index of selected topic", required: true }
    ],
    renderAndWaitForResponse: ({ args, respond, status }) => (
      <div className="p-4 border rounded bg-white shadow-sm">
        <h2 className="text-lg font-bold mb-2">Select Content Topic</h2>
        <p className="text-sm text-gray-500 mb-4">
          Choose a topic to generate content for
        </p>
        <div className="space-y-4 max-h-96 overflow-y-auto">
          {state?.topics?.map((topic, idx) => (
            <div
              key={idx}
              className={`p-3 border rounded cursor-pointer transition-colors ${
                state.selected_topic === topic ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'
              }`}
              onClick={() => {
                const newState = { ...state, selected_topic: topic };
                setState && setState(newState);
                respond && respond(idx);
              }}
            >
              <h3 className="font-bold">{topic.title}</h3>
              <p className="text-sm">{topic.description}</p>
              <div className="text-xs text-gray-500 mt-2">
                Source: {topic.source_type} • 
                Content types: {topic.content_types.join(", ")}
              </div>
            </div>
          ))}
        </div>
        {state?.topics?.length === 0 && (
          <p className="text-center py-8 text-gray-400">
            No topics generated yet. Please wait...
          </p>
        )}
      </div>
    )
  });

  // Content Editor Action
  useCopilotAction({
    name: "confirm_content",
    description: "Confirm edited content is ready to save",
    parameters: [],
    renderAndWaitForResponse: ({ args, respond, status }) => (
      <div className="p-4 border rounded bg-white shadow-sm">
        <h2 className="text-lg font-bold mb-4">Edit & Publish Content</h2>
        
        {/* Content Form */}
        <div className="space-y-4">
          {/* Channel */}
          <div>
            <label className="block text-sm font-medium mb-1">Channel</label>
            <select
              className="w-full p-2 border rounded"
              value={state?.content_record?.channel || ""}
              onChange={(e) => setState && setState({
                ...state,
                content_record: {
                  ...state.content_record,
                  channel: e.target.value
                }
              })}
            >
              <option value="">Select a channel</option>
              <option value="blog">Blog</option>
              <option value="twitter">Twitter</option>
              <option value="linkedin">LinkedIn</option>
              <option value="github">GitHub</option>
            </select>
          </div>
          
          {/* Title */}
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <input
              type="text"
              className="w-full p-2 border rounded"
              value={state?.content_record?.title || ""}
              onChange={(e) => setState && setState({
                ...state,
                content_record: {
                  ...state.content_record,
                  title: e.target.value
                }
              })}
            />
          </div>
          
          {/* Summary */}
          <div>
            <label className="block text-sm font-medium mb-1">Summary</label>
            <textarea
              className="w-full p-2 border rounded"
              rows={3}
              value={state?.content_record?.summary || ""}
              onChange={(e) => setState && setState({
                ...state,
                content_record: {
                  ...state.content_record,
                  summary: e.target.value
                }
              })}
            />
          </div>
          
          {/* Content */}
          <div>
            <label className="block text-sm font-medium mb-1">Content</label>
            <textarea
              className="w-full p-2 border rounded"
              rows={10}
              value={state?.content_record?.content || ""}
              onChange={(e) => setState && setState({
                ...state,
                content_record: {
                  ...state.content_record,
                  content: e.target.value
                }
              })}
            />
          </div>
          
          {/* Type */}
          <div>
            <label className="block text-sm font-medium mb-1">Type</label>
            <select
              className="w-full p-2 border rounded"
              value={state?.content_record?.type || ""}
              onChange={(e) => setState && setState({
                ...state,
                content_record: {
                  ...state.content_record,
                  type: e.target.value
                }
              })}
            >
              <option value="">Select content type</option>
              <option value="blog_post">Blog Post</option>
              <option value="code_example">Code Example</option>
              <option value="social_media">Social Media</option>
            </select>
          </div>
        </div>
        
        {/* Buttons */}
        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={() => respond && respond("CANCEL")}
            disabled={status !== "executing"}
            className="border px-4 py-2 rounded text-gray-700 disabled:opacity-50"
          >
            Edit More
          </button>
          <button
            onClick={() => {
              if (setState && state) {
                setState({
                  ...state,
                  copilotkit: {
                    ...state.copilotkit,
                    metadata: { ...(state.copilotkit?.metadata || {}), confirmed: true }
                  }
                });
              }
              respond && respond("CONFIRM");
            }}
            disabled={status !== "executing"}
            className="bg-blue-500 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            Save & Publish
          </button>
        </div>
      </div>
    )
  });

  // Status display
  const renderStatus = () => {
    if (state?.status) {
      return (
        <div className="p-4 bg-gray-100 border-b">
          <p className="text-sm font-medium">{state.status}</p>
        </div>
      );
    }
    if (state?.error) {
      return (
        <div className="p-4 bg-red-50 text-red-700 border-b">
          <p className="text-sm font-medium">Error: {state.error}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {renderStatus()}
      
      <div className="max-w-3xl mx-auto bg-white rounded-lg shadow p-6">
        <h1 className="text-2xl font-bold mb-6">DevRel Content Publisher</h1>
        
        {/* Stepper */}
        <div className="mb-8">
          <ol className="flex items-center w-full">
            <li className={`flex w-full items-center ${activeStep > 1 ? 'text-blue-600' : 'text-gray-500'}`}>
              <span className={`flex items-center justify-center w-8 h-8 border rounded-full shrink-0 ${activeStep >= 1 ? 'border-blue-600 bg-blue-100' : ''}`}>1</span>
              <span className="ml-2 text-sm">Repository</span>
              <div className="w-full bg-gray-200 h-0.5 ml-2"></div>
            </li>
            <li className={`flex w-full items-center ${activeStep > 2 ? 'text-blue-600' : 'text-gray-500'}`}>
              <span className={`flex items-center justify-center w-8 h-8 border rounded-full shrink-0 ${activeStep >= 2 ? 'border-blue-600 bg-blue-100' : ''}`}>2</span>
              <span className="ml-2 text-sm">Select Topic</span>
              <div className="w-full bg-gray-200 h-0.5 ml-2"></div>
            </li>
            <li className={`flex items-center ${activeStep > 3 ? 'text-blue-600' : 'text-gray-500'}`}>
              <span className={`flex items-center justify-center w-8 h-8 border rounded-full shrink-0 ${activeStep >= 3 ? 'border-blue-600 bg-blue-100' : ''}`}>3</span>
              <span className="ml-2 text-sm">Edit & Publish</span>
            </li>
          </ol>
        </div>

        <div className="p-4">
          <div className="prose max-w-none">
            {state?.content_record?.content && (
              <div>
                <h2>{state.content_record.title || "Untitled"}</h2>
                <p className="text-gray-500">{state.content_record.summary || ""}</p>
                <hr className="my-4" />
                <Markdown content={state.content_record.content} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
