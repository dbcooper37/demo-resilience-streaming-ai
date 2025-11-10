package com.demo.websocket.exception;

public class MessageNotFoundException extends RuntimeException {
    
    public MessageNotFoundException(String message) {
        super(message);
    }
}
