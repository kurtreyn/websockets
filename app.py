#!/usr/bin/env python

import asyncio
import json
import secrets

import websockets

from connect4 import PLAYER1, PLAYER2, Connect4


JOIN = {}


async def error(websocket, message):
    """
    Send an error message.

    """
    event = {
        "type": "error",
        "message": message,
    }
    await websocket.send(json.dumps(event))


async def replay(websocket, game):
    """
    Send previous moves.

    """
    # Make a copy to avoid an exception if game.moves changes while iteration
    # is in progress. If a move is played while replay is running, moves will
    # be sent out of order but each move will be sent once and eventually the
    # UI will be consistent.
    for player, column, row in game.moves.copy():
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row,
        }
        await websocket.send(json.dumps(event))


async def play(websocket, game, player, connected):
    """
    3. First called by PLAYER1, then by PLAYER2.
    Receive and process moves from a player.

    """
    async for message in websocket:
        # Parse a "play" event from the UI.
        event = json.loads(message)
        assert event["type"] == "play"
        column = event["column"]
        print(f"def play - websocket: {websocket}")
        print(f"def play - game: {game}")
        print(f"def play - player: {player}")
        print(f"def play - connected: {connected}")

        try:
            # Play the move.
            row = game.play(player, column)
        except RuntimeError as exc:
            # Send an "error" event if the move was illegal.
            await error(websocket, str(exc))
            continue

        # Send a "play" event to update the UI.
        event = {
            "type": "play",
            "player": player,
            "column": column,
            "row": row,
        }
        websockets.broadcast(connected, json.dumps(event))

        # If move is winning, send a "win" event.
        if game.winner is not None:
            event = {
                "type": "win",
                "player": game.winner,
            }
            websockets.broadcast(connected, json.dumps(event))


async def start(websocket):
    """
    2. Once the first player is connected, the game starts
    Handle a connection from the first player: start a new game.

    """
    # Initialize a Connect Four game, the set of WebSocket connections
    # receiving moves from this game, and secret access tokens.
    game = Connect4()
    connected = {websocket}

    join_key = secrets.token_urlsafe(12)
    JOIN[join_key] = game, connected
    print(f"def start - game: {game}")
    print(f"def start - connected: {connected}")
    print(f"def start - join_key: {join_key}")
    print(f"def start - JOIN[join_key]: {JOIN[join_key]}")

    try:
        # Send the secret access tokens to the browser of the first player,
        # where they'll be used for building "join" and "watch" links.
        event = {
            "type": "init",
            "join": join_key,
            "join_url": f"http://localhost:8000/?join=/{join_key}",
        }
        print(f"def start - event: {event}")
        await websocket.send(json.dumps(event))
        # Receive and process moves from the first player.
        await play(websocket, game, PLAYER1, connected)
    finally:
        del JOIN[join_key]


async def join(websocket, join_key):
    """
    Handle a connection from the second player: join an existing game.

    """
    # Find the Connect Four game.
    try:
        game, connected = JOIN[join_key]
    except KeyError:
        await error(websocket, "Game not found.")
        return

    # Register to receive moves from this game.
    connected.add(websocket)
    try:
        # Send the first move, in case the first player already played it.
        await replay(websocket, game)
        # Receive and process moves from the second player.
        await play(websocket, game, PLAYER2, connected)
    finally:
        connected.remove(websocket)


async def handler(websocket):
    """
    1. Process starts here
    Handle a connection and dispatch it according to who is connecting.

    """
    # Receive and parse the "init" event from the UI.
    message = await websocket.recv()
    event = json.loads(message)
    assert event["type"] == "init"
    print(f"def handler - message: {message}")
    print(f"def handler - event: {event}")

    if "join" in event:
        # Second player joins an existing game.
        await join(websocket, event["join"])
    else:
        # Start game when first player connects
        await start(websocket)


async def main():
    async with websockets.serve(handler, "", 8080):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())