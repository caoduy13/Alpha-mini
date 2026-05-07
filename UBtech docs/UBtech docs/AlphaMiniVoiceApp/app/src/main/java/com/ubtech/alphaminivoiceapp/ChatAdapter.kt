package com.ubtech.alphaminivoiceapp

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.ubtech.alphaminivoiceapp.databinding.ItemChatBinding

class ChatAdapter(private val items: MutableList<ChatWebSocket.ChatMessage>) :
    RecyclerView.Adapter<ChatAdapter.ViewHolder>() {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemChatBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(items[position])
    }

    override fun getItemCount() = items.size

    fun update(newList: List<ChatWebSocket.ChatMessage>) {
        items.clear()
        items.addAll(newList)
        notifyDataSetChanged()
    }

    class ViewHolder(private val binding: ItemChatBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(msg: ChatWebSocket.ChatMessage) {
            binding.textSender.text = if (msg.sender == "user") "Bạn" else "Alpha Mini"
            binding.textMessage.text = msg.text
        }
    }
}
