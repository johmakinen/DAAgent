"""Synthesizer agent for creating final user-facing responses."""
import mlflow
import logging
from pydantic_ai import Agent, ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict
from app.core.models import AgentResponse, SynthesizerOutput, PlotSpec, ExecutionPlan
from app.core.config import Config
from app.utils.plot_generator import PlotGenerator
from app.utils.response_formatter import ResponseFormatter

mlflow.pydantic_ai.autolog()

logger = logging.getLogger(__name__)


class SynthesizerDeps(BaseModel):
    """Dependencies for SynthesizerAgent tools."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    plot_generator: Optional[PlotGenerator] = None


class SynthesizerAgent:
    """
    Agent for synthesizing clear, natural language responses from agent outputs.
    Can decide if plots are needed and generate them for database query results.
    """
    
    def __init__(self, prompt_template: str, plot_generator: Optional[PlotGenerator] = None):
        """
        Initialize the synthesizer agent.
        
        Args:
            prompt_template: The prompt template/instructions for the agent
            plot_generator: Optional PlotGenerator instance for creating plots
        """
        self.plot_generator = plot_generator
        
        # Get model configuration for this agent
        model_config = Config.get_model('synthesizer')
        
        # Convert AzureModelConfig to OpenAIChatModel
        model = OpenAIChatModel(
            model_config.name,
            provider=model_config.provider,
        )
        
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=SynthesizerOutput,
            deps_type=SynthesizerDeps,
            name="synthesizer-agent"
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
            execution_plan: Optional execution plan with plot requirements
            
        Returns:
            Agent result with AgentResponse output (includes plot_spec if plot was generated)
        """
        logger.info("LLM Call: SynthesizerAgent - synthesizing final user-facing response")
        
        # Determine if plot should be generated BEFORE text synthesis
        # Use plan's plot requirements if available, otherwise we'll check synthesizer output after first run
        should_plot = False
        plot_type = None
        plot_columns = None
        
        if execution_plan and execution_plan.requires_plot:
            should_plot = True
            plot_type = execution_plan.plot_type
            logger.info(f"Plot required by execution_plan: plot_type={plot_type}")
        
        # Generate plot FIRST if execution plan requires it (before text synthesis)
        plot_spec_dict = None
        plot_metadata = None
        
        if (should_plot and 
            self.plot_generator is not None and 
            database_data is not None and 
            len(database_data) > 0 and
            plot_type is not None):
            
            logger.info(f"Generating plot first: type={plot_type}, data_rows={len(database_data)}")
            try:
                plot_spec_dict = await self.plot_generator.generate_plot(
                    data=database_data,
                    plot_type=plot_type,
                    question=user_question or "",
                    columns=plot_columns
                )
                
                if plot_spec_dict:
                    # Extract plot metadata for text synchronization
                    plot_metadata = self.plot_generator.extract_plot_metadata(plot_spec_dict)
                    logger.info(f"Successfully generated plot_spec: type={plot_type}, metadata={plot_metadata is not None}")
                else:
                    logger.warning("Plot generation returned None")
            except Exception as e:
                # Log error but don't fail the response
                logger.warning(f"Failed to generate plot: {e}", exc_info=True)
        else:
            logger.info(f"Plot generation skipped (will check after agent run): should_plot={should_plot}, plot_generator={self.plot_generator is not None}, database_data={database_data is not None and len(database_data) > 0 if database_data else False}, plot_type={plot_type}")
        
        # Update context with plot metadata if available
        if plot_metadata:
            context = ResponseFormatter.add_plot_metadata_to_context(context, plot_metadata)
        
        # Now run the synthesizer agent with updated context
        deps = SynthesizerDeps(plot_generator=self.plot_generator)
        if message_history:
            result = await self.agent.run(context, deps=deps, message_history=message_history)
        else:
            result = await self.agent.run(context, deps=deps)
        
        synthesizer_output = result.output
        
        # If plot wasn't generated from execution plan, check if synthesizer wants one
        if not plot_spec_dict and synthesizer_output.should_generate_plot:
            should_plot = True
            plot_type = synthesizer_output.plot_type
            plot_columns = synthesizer_output.plot_columns
            
            if (self.plot_generator is not None and 
                database_data is not None and 
                len(database_data) > 0 and
                plot_type is not None):
                
                logger.info(f"Generating plot from synthesizer output: type={plot_type}, data_rows={len(database_data)}")
                try:
                    plot_spec_dict = await self.plot_generator.generate_plot(
                        data=database_data,
                        plot_type=plot_type,
                        question=user_question or "",
                        columns=plot_columns
                    )
                    
                    if plot_spec_dict:
                        # Extract plot metadata (for future use, but text already generated)
                        plot_metadata = self.plot_generator.extract_plot_metadata(plot_spec_dict)
                        logger.info(f"Successfully generated plot_spec: type={plot_type}")
                except Exception as e:
                    logger.warning(f"Failed to generate plot: {e}", exc_info=True)
        
        # Convert to AgentResponse
        agent_response = AgentResponse(
            message=synthesizer_output.message,
            confidence=synthesizer_output.confidence,
            requires_followup=synthesizer_output.requires_followup,
            metadata=synthesizer_output.metadata
        )
        
        # Attach plot spec if it was generated
        if plot_spec_dict:
            agent_response.plot_spec = PlotSpec(
                spec=plot_spec_dict,
                plot_type=plot_type or "unknown"
            )
        
        # Update result output to be AgentResponse
        result.output = agent_response
        return result

