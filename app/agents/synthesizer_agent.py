"""Synthesizer agent for creating final user-facing responses."""
import mlflow
from pydantic_ai import Agent, ModelMessage
from typing import Optional, List, Dict
from app.core.models import AgentResponse, SynthesizerOutput, PlotSpec, ExecutionPlan
from app.utils.plot_generator import PlotGenerator

mlflow.pydantic_ai.autolog()
class SynthesizerAgent:
    """
    Agent for synthesizing clear, natural language responses from agent outputs.
    Can decide if plots are needed and generate them for database query results.
    """
    
    def __init__(self, model: str, prompt_template: str, plot_generator: Optional[PlotGenerator] = None):
        """
        Initialize the synthesizer agent.
        
        Args:
            model: The model identifier for the agent
            prompt_template: The prompt template/instructions for the agent
            plot_generator: Optional PlotGenerator instance for creating plots
        """
        self.plot_generator = plot_generator
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=SynthesizerOutput
        )
    
    async def run(
        self,
        context: str,
        message_history: Optional[List[ModelMessage]] = None,
        database_data: Optional[List[Dict]] = None,
        user_question: Optional[str] = None,
        execution_plan: Optional[ExecutionPlan] = None
    ):
        """
        Run the synthesizer agent.
        
        Args:
            context: The context containing agent output to synthesize
            message_history: Optional message history for conversation context
            database_data: Optional database result data (for plot generation)
            user_question: Optional original user question (for plot context)
            
        Returns:
            Agent result with AgentResponse output (includes plot_spec if plot was generated)
        """
        result = await (self.agent.run(context, message_history=message_history) if message_history else self.agent.run(context))
        
        synthesizer_output = result.output
        
        # Convert to AgentResponse
        agent_response = AgentResponse(
            message=synthesizer_output.message,
            confidence=synthesizer_output.confidence,
            requires_followup=synthesizer_output.requires_followup,
            metadata=synthesizer_output.metadata
        )
        
        # Determine if plot should be generated
        # Use plan's plot requirements if available, otherwise use synthesizer output
        should_plot = False
        plot_type = None
        
        if execution_plan and execution_plan.requires_plot:
            should_plot = True
            plot_type = execution_plan.plot_type or synthesizer_output.plot_type
        elif synthesizer_output.should_generate_plot:
            should_plot = True
            plot_type = synthesizer_output.plot_type
        
        # Generate plot if needed and we have the required data
        if (should_plot and 
            self.plot_generator is not None and 
            database_data is not None and 
            len(database_data) > 0 and
            plot_type is not None):
            
            try:
                plot_spec_dict = await self.plot_generator.generate_plot(
                    data=database_data,
                    plot_type=plot_type,
                    question=user_question or "",
                    columns=synthesizer_output.plot_columns
                )
                
                if plot_spec_dict:
                    agent_response.plot_spec = PlotSpec(
                        spec=plot_spec_dict,
                        plot_type=plot_type
                    )
            except Exception as e:
                # Log error but don't fail the response
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to generate plot: {e}")
        
        # Update result output to be AgentResponse
        result.output = agent_response
        return result

