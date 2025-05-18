"use client";

import { useCoAgent, useCopilotAction, useCoAgentStateRender } from "@copilotkit/react-core";
import { CopilotKitCSSProperties, CopilotSidebar } from "@copilotkit/react-ui";
import { useState } from "react";

export default function CopilotKitPage() {
  const [themeColor, setThemeColor] = useState("#6366f1");

  // 🪁 Frontend Actions: https://docs.copilotkit.ai/guides/frontend-actions
  useCopilotAction({
    name: "setThemeColor",
    parameters: [{
      name: "themeColor",
      description: "The theme color to set. Make sure to pick nice colors.",
      required: true, 
    }],
    handler({ themeColor }) {
      setThemeColor(themeColor);
    },
  });

  return (
    <main style={{ "--copilot-kit-primary-color": themeColor } as CopilotKitCSSProperties}>
      <YourMainContent themeColor={themeColor} />
      <CopilotSidebar
        clickOutsideToClose={false}
        defaultOpen={true}
        labels={{
          title: "Popup Assistant",
          initial: "👋 Hi, there! You're chatting with an agent."
        }}
      />
    </main>
  );
}

// Define the state of the agent, should match the state of the agent in your LangGraph.
type ContentRecord = {
  channel: string;
  title: string;
  summary: string;
  content: string;
  type: string;
  id?: string;
};

type AgentState = {
  content_record?: ContentRecord;
  status?: string;
  error?: string;
};

function YourMainContent({ themeColor }: { themeColor: string }) {
  // Render the agent's state in the chat using useCoAgentStateRender
  useCoAgentStateRender<AgentState>({
    name: "sample_agent",
    render: ({ state }) => (
      <div className="w-full flex flex-col items-center mt-8">
        {state?.status && (
          <div className="mb-2 text-blue-600 font-semibold">{state.status}</div>
        )}
        {state?.error && (
          <div className="mb-2 text-red-600 font-semibold">{state.error}</div>
        )}
        {state?.content_record && (
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-xl w-full">
            <h2 className="text-xl font-bold mb-2">{state.content_record.title}</h2>
            <div className="mb-2 text-gray-600">{state.content_record.summary}</div>
            <div className="prose prose-sm max-w-none" style={{ whiteSpace: "pre-wrap" }}>
              {state.content_record.content}
            </div>
            <div className="mt-4 text-sm text-gray-400">
              Channel: {state.content_record.channel} | Type: {state.content_record.type}
            </div>
          </div>
        )}
      </div>
    ),
  });

  return (
    <div
      style={{ backgroundColor: themeColor }}
      className="h-screen w-screen flex justify-center items-center flex-col transition-colors duration-300"
    >
      <span className="text-white text-lg font-semibold">DevRel Publishing Agent</span>
    </div>
  );
}

// Simple sun icon for the weather card
function SunIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-14 h-14 text-yellow-200">
      <circle cx="12" cy="12" r="5" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" strokeWidth="2" stroke="currentColor" />
    </svg>
  );
}

// Weather card component where the location and themeColor are based on what the agent
// sets via tool calls.
function WeatherCard({ location, themeColor }: { location?: string, themeColor: string }) {
  return (
    <div
    style={{ backgroundColor: themeColor }}
    className="rounded-xl shadow-xl mt-6 mb-4 max-w-md w-full"
  >
    <div className="bg-white/20 p-4 w-full">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-white capitalize">{location}</h3>
          <p className="text-white">Current Weather</p>
        </div>
        <SunIcon />
      </div>
      
      <div className="mt-4 flex items-end justify-between">
        <div className="text-3xl font-bold text-white">70°</div>
        <div className="text-sm text-white">Clear skies</div>
      </div>
      
      <div className="mt-4 pt-4 border-t border-white">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-white text-xs">Humidity</p>
            <p className="text-white font-medium">45%</p>
          </div>
          <div>
            <p className="text-white text-xs">Wind</p>
            <p className="text-white font-medium">5 mph</p>
          </div>
          <div>
            <p className="text-white text-xs">Feels Like</p>
            <p className="text-white font-medium">72°</p>
          </div>
        </div>
      </div>
    </div>
  </div>
  );
}
