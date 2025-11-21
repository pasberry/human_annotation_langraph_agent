"""CLI application for evidencing agent."""
import json
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from agent.graph import agent
from feedback.collector import feedback_collector
from feedback.processor import feedback_processor
from storage import db


console = Console()


@click.group()
def cli():
    """Evidencing Agent CLI - Asset scoping decisions with human feedback."""
    pass


@cli.command()
@click.argument("asset_uri")
@click.argument("commitment")
@click.option("--query", is_flag=True, help="Treat commitment as natural language query instead of ID")
def decide(asset_uri: str, commitment: str, query: bool):
    """
    Make a scoping decision for an asset and commitment.

    Examples:
        # By commitment ID/name
        cli decide database.customer_data.production "Customer Data Usage Policy"

        # By natural language query
        cli decide database.user_data.ads_training "no user data for ads" --query
    """
    console.print(f"\n[bold]Analyzing asset:[/bold] {asset_uri}")
    if query:
        console.print(f"[bold]Commitment Query:[/bold] \"{commitment}\"")
        console.print("[dim]Searching for relevant commitments...[/dim]\n")
    else:
        console.print(f"[bold]Commitment:[/bold] {commitment}\n")

    with console.status("[bold green]Processing...") as status:
        # Run the agent
        if query:
            result = agent.run(
                asset_uri=asset_uri,
                commitment_query=commitment
            )
        else:
            result = agent.run(
                asset_uri=asset_uri,
                commitment_id=commitment
            )

    # Check for errors
    if result.errors:
        console.print("[bold red]Errors occurred:[/bold]")
        for error in result.errors:
            console.print(f"  - {error}")
        return

    if not result.response:
        console.print("[bold red]No response generated[/bold]")
        return

    # Display decision
    response = result.response

    if response.decision == "insufficient-data":
        console.print(Panel(
            "[bold yellow]⚠️  INSUFFICIENT DATA TO DECIDE[/bold yellow]",
            style="yellow"
        ))
        console.print(f"\n{response.reasoning}\n")

        if response.missing_information:
            console.print("[bold]Missing Information:[/bold]")
            for item in response.missing_information:
                console.print(f"  • {item}")
            console.print()

        if response.clarifying_questions:
            console.print("[bold]Clarifying Questions:[/bold]")
            for q in response.clarifying_questions:
                console.print(f"  • {q}")
            console.print()

        if response.partial_analysis:
            console.print(Panel(
                response.partial_analysis,
                title="Partial Analysis",
                style="dim"
            ))

    else:
        # Display confident decision
        decision_color = "green" if response.decision == "in-scope" else "blue"
        decision_text = "✅ IN-SCOPE" if response.decision == "in-scope" else "❌ OUT-OF-SCOPE"

        console.print(Panel(
            f"[bold {decision_color}]{decision_text}[/bold {decision_color}]",
            style=decision_color
        ))

        console.print(f"\n[bold]Confidence:[/bold] {response.confidence_level} ({response.confidence_score:.2f})\n")
        console.print(f"[bold]Reasoning:[/bold]\n{response.reasoning}\n")

        # Evidence (expandable)
        if response.evidence:
            console.print("[bold]📊 Evidence:[/bold]")
            console.print(f"  [dim]Commitment Analysis:[/dim] {response.evidence.commitment_analysis}")
            console.print(f"  [dim]Decision Rationale:[/dim] {response.evidence.decision_rationale}")
            if response.evidence.asset_characteristics:
                console.print(f"  [dim]Asset Characteristics:[/dim]")
                for char in response.evidence.asset_characteristics:
                    console.print(f"    • {char}")
            console.print()

        # Commitment references
        if response.commitment_references:
            console.print("[bold]📚 Commitment References:[/bold]")
            for ref in response.commitment_references:
                console.print(f"  [dim]Chunk {ref.chunk_id}:[/dim] {ref.text[:100]}...")
                if ref.relevance:
                    console.print(f"    → {ref.relevance}")
            console.print()

        # Similar decisions
        if response.similar_decisions:
            console.print("[bold]🔍 Similar Past Decisions:[/bold]")
            for sim in response.similar_decisions:
                console.print(f"  • {sim.asset_uri} → {sim.decision} (similarity: {sim.similarity_score:.2f})")
                console.print(f"    {sim.how_it_influenced}")
            console.print()

    # Decision ID for feedback
    console.print(f"[dim]Decision ID: {result.decision.id}[/dim]")
    console.print(f"[dim]Session ID (Thread ID): {result.session_id}[/dim]")
    console.print(f"[dim]💾 View checkpoints: cli checkpoint-history {result.session_id}[/dim]\n")


@cli.command()
@click.argument("decision_id")
@click.option("--rating", type=click.Choice(["up", "down"]), required=True, help="Thumbs up or down")
@click.option("--reason", required=True, help="Why this was correct/incorrect")
@click.option("--correction", default=None, help="For thumbs down: correct decision and reasoning")
def feedback(decision_id: str, rating: str, reason: str, correction: str | None):
    """
    Submit feedback for a decision.

    Example:
        cli feedback abc-123 --rating down --reason "Database doesn't contain PII" --correction "Should be out-of-scope"
    """
    console.print(f"\n[bold]Submitting feedback for decision:[/bold] {decision_id}\n")

    try:
        feedback_entry = feedback_collector.submit_feedback(
            decision_id=decision_id,
            rating=rating,
            human_reason=reason,
            human_correction=correction
        )

        emoji = "👍" if rating == "up" else "👎"
        console.print(Panel(
            f"[bold green]{emoji} Feedback submitted successfully![/bold green]\n"
            f"Feedback ID: {feedback_entry.id}",
            style="green"
        ))

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")

# Commitment ingestion removed - use: python -m ingestion.commitment_ingestion <path>


@cli.command()
def list_commitments():
    """List all commitments in the system."""
    commitments = db.list_commitments()

    if not commitments:
        console.print("[yellow]No commitments found. Add some with 'add-commitment'[/yellow]")
        return

    table = Table(title="Commitments")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("ID", style="dim")
    table.add_column("Created", style="yellow")

    for c in commitments:
        table.add_row(
            c.name,
            (c.description[:50] + "...") if c.description and len(c.description) > 50 else (c.description or "-"),
            c.id[:8],
            c.created_at.strftime("%Y-%m-%d")
        )

    console.print(table)


@cli.command()
@click.option("--commitment", default=None, help="Filter by commitment")
@click.option("--limit", default=10, help="Number of decisions to show")
def list_decisions(commitment: str | None, limit: int):
    """List recent scoping decisions."""
    decisions = db.list_scoping_decisions(commitment_id=commitment, limit=limit)

    if not decisions:
        console.print("[yellow]No decisions found[/yellow]")
        return

    table = Table(title=f"Recent Decisions (last {limit})")
    table.add_column("Asset", style="cyan")
    table.add_column("Commitment", style="magenta")
    table.add_column("Decision", style="green")
    table.add_column("Confidence", style="yellow")
    table.add_column("ID", style="dim")

    for d in decisions:
        decision_emoji = "✅" if d["decision"] == "in-scope" else ("❌" if d["decision"] == "out-of-scope" else "⚠️")
        table.add_row(
            d["asset_uri"],
            d["commitment_name"],
            f"{decision_emoji} {d['decision']}",
            f"{d['confidence_level']} ({d['confidence_score']:.2f})",
            d["id"][:8]
        )

    console.print(table)


@cli.command()
@click.option("--commitment", default=None, help="Filter by commitment")
def stats(commitment: str | None):
    """Show feedback statistics."""
    stats = feedback_processor.get_feedback_stats(commitment_id=commitment)

    console.print(Panel(
        f"[bold]Total Feedback:[/bold] {stats['total']}\n"
        f"[bold green]👍 Thumbs Up:[/bold green] {stats['thumbs_up']}\n"
        f"[bold red]👎 Thumbs Down:[/bold red] {stats['thumbs_down']}\n"
        f"[bold]Accuracy:[/bold] {stats['accuracy']:.1%}",
        title="Feedback Statistics",
        style="blue"
    ))


@cli.command()
@click.argument("decision_id")
def list_feedback(decision_id: str):
    """
    List all feedback for a specific decision.

    Example:
        cli list-feedback abc-123-def
    """
    console.print(f"\n[bold]Feedback for Decision:[/bold] {decision_id}\n")

    # Get the decision
    decision = db.get_scoping_decision(decision_id)
    if not decision:
        console.print(f"[bold red]Decision not found:[/bold red] {decision_id}")
        return

    # Show decision summary
    console.print(Panel(
        f"[bold]Asset:[/bold] {decision['asset_uri']}\n"
        f"[bold]Commitment:[/bold] {decision['commitment_name']}\n"
        f"[bold]Decision:[/bold] {decision['decision']}\n"
        f"[bold]Confidence:[/bold] {decision['confidence_level']} ({decision['confidence_score']:.2f})",
        title="Original Decision",
        style="cyan"
    ))

    # Get feedback for this decision
    feedback_list = db.list_feedback(decision_id=decision_id)

    if not feedback_list:
        console.print("\n[yellow]No feedback found for this decision[/yellow]\n")
        return

    console.print(f"\n[bold]Found {len(feedback_list)} feedback entries:[/bold]\n")

    for idx, fb in enumerate(feedback_list, 1):
        rating_emoji = "👍" if fb.rating == "up" else "👎"
        rating_color = "green" if fb.rating == "up" else "red"

        console.print(Panel(
            f"[bold {rating_color}]{rating_emoji} {fb.rating.upper()}[/bold {rating_color}]\n\n"
            f"[bold]Human Reason:[/bold]\n{fb.human_reason}\n"
            + (f"\n[bold]Correction:[/bold]\n{fb.human_correction}\n" if fb.human_correction else "") +
            f"\n[dim]Submitted: {fb.created_at.strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n"
            f"[dim]Feedback ID: {fb.id}[/dim]",
            title=f"Feedback #{idx}",
            style=rating_color
        ))

    console.print()


@cli.command()
@click.argument("thread_id")
def checkpoint_history(thread_id: str):
    """
    Show checkpoint history for a decision thread.

    Displays all checkpoints saved during the decision-making process.

    Example:
        cli checkpoint-history abc-123-session-id
    """
    console.print(f"\n[bold]Checkpoint History for Thread:[/bold] {thread_id}\n")

    try:
        checkpoints = agent.get_checkpoint_history(thread_id)

        if not checkpoints:
            console.print("[yellow]No checkpoints found for this thread[/yellow]")
            return

        console.print(f"Found {len(checkpoints)} checkpoints:\n")

        for idx, checkpoint in enumerate(checkpoints):
            values = checkpoint.get("values", {})
            next_nodes = checkpoint.get("next", [])

            console.print(f"[bold cyan]Checkpoint {idx + 1}[/bold cyan]")

            if next_nodes:
                console.print(f"  [dim]Next nodes:[/dim] {', '.join(next_nodes)}")

            # Show key state information
            if values:
                state_info = []
                if "asset" in values and values["asset"]:
                    state_info.append(f"Asset: {values['asset'].get('raw_uri', 'N/A')}")
                if "commitment_name" in values and values["commitment_name"]:
                    state_info.append(f"Commitment: {values['commitment_name']}")
                if "confidence" in values and values["confidence"]:
                    conf = values["confidence"]
                    state_info.append(f"Confidence: {conf.get('level', 'N/A')} ({conf.get('score', 0):.2f})")
                if "response" in values and values["response"]:
                    resp = values["response"]
                    state_info.append(f"Decision: {resp.get('decision', 'N/A')}")

                for info in state_info:
                    console.print(f"  {info}")

            console.print()

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")


@cli.command()
@click.argument("thread_id")
def checkpoint_state(thread_id: str):
    """
    Show current checkpoint state for a thread.

    Example:
        cli checkpoint-state abc-123-session-id
    """
    console.print(f"\n[bold]Current State for Thread:[/bold] {thread_id}\n")

    try:
        state = agent.get_current_state(thread_id)

        if not state:
            console.print("[yellow]No state found for this thread[/yellow]")
            return

        # Display state info
        console.print(Panel(
            f"[bold]Asset:[/bold] {state.asset_uri}\n"
            f"[bold]Commitment:[/bold] {state.commitment_name or state.commitment_id}\n"
            f"[bold]Session ID:[/bold] {state.session_id}",
            title="Thread State",
            style="cyan"
        ))

        if state.response:
            console.print(f"\n[bold]Decision:[/bold] {state.response.decision}")
            console.print(f"[bold]Confidence:[/bold] {state.response.confidence_level} ({state.response.confidence_score:.2f})")
            console.print(f"\n[bold]Reasoning:[/bold]\n{state.response.reasoning}")

        if state.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in state.errors:
                console.print(f"  - {error}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")


if __name__ == "__main__":
    cli()
