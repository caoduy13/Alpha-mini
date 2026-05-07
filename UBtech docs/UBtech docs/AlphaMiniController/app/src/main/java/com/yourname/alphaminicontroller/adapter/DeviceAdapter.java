package com.yourname.alphaminicontroller.adapter;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.card.MaterialCardView;
import com.yourname.alphaminicontroller.R;
import com.yourname.alphaminicontroller.model.RobotDevice;

import java.util.ArrayList;
import java.util.List;

/**
 * RecyclerView adapter for displaying discovered Bluetooth devices.
 * AlphaMini devices are visually highlighted.
 */
public class DeviceAdapter extends RecyclerView.Adapter<DeviceAdapter.ViewHolder> {

    public interface OnDeviceClickListener {
        void onDeviceClicked(RobotDevice device);
    }

    private final List<RobotDevice> devices = new ArrayList<>();
    private final OnDeviceClickListener listener;
    private int selectedPosition = -1;

    public DeviceAdapter(OnDeviceClickListener listener) {
        this.listener = listener;
    }

    /** Add a device if not already in the list (by MAC). AlphaMini devices go first. */
    public void addDevice(RobotDevice device) {
        for (RobotDevice d : devices) {
            if (d.getMacAddress().equals(device.getMacAddress())) return;
        }
        if (device.isAlphaMini()) {
            devices.add(0, device); // Insert at top
            notifyItemInserted(0);
        } else {
            devices.add(device);
            notifyItemInserted(devices.size() - 1);
        }
    }

    public void clearDevices() {
        devices.clear();
        selectedPosition = -1;
        notifyDataSetChanged();
    }

    /** Returns the currently selected device, or null if none is selected. */
    public RobotDevice getSelectedDevice() {
        if (selectedPosition >= 0 && selectedPosition < devices.size()) {
            return devices.get(selectedPosition);
        }
        return null;
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_device, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        RobotDevice device = devices.get(position);
        holder.tvName.setText(device.getName());
        holder.tvMac.setText(device.getMacAddress());
        holder.tvBadge.setVisibility(device.isAlphaMini() ? View.VISIBLE : View.GONE);

        boolean selected = (position == selectedPosition);
        holder.cardView.setStrokeWidth(selected ? 3 : 0);
        holder.cardView.setCardElevation(selected ? 8f : 2f);

        holder.cardView.setOnClickListener(v -> {
            int prev = selectedPosition;
            selectedPosition = holder.getAdapterPosition();
            notifyItemChanged(prev);
            notifyItemChanged(selectedPosition);
            listener.onDeviceClicked(device);
        });
    }

    @Override
    public int getItemCount() { return devices.size(); }

    static class ViewHolder extends RecyclerView.ViewHolder {
        final MaterialCardView cardView;
        final TextView tvName;
        final TextView tvMac;
        final TextView tvBadge;

        ViewHolder(@NonNull View itemView) {
            super(itemView);
            cardView = (MaterialCardView) itemView;
            tvName   = itemView.findViewById(R.id.tv_device_name);
            tvMac    = itemView.findViewById(R.id.tv_device_mac);
            tvBadge  = itemView.findViewById(R.id.tv_badge);
        }
    }
}
