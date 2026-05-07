package com.communityuni.adapter;

import android.app.Activity;
import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.communityuni.alphaminidiscovery.R;
import com.ubtrobot.small.action.SmallAction;

public class SmallActionAdapter extends ArrayAdapter<SmallAction> {
    Activity context;
    int resource;
    public SmallActionAdapter(@NonNull Activity context, int resource) {
        super(context, resource);
        this.context=context;
        this.resource=resource;
    }
    @NonNull
    @Override
    public View getView(int position, @Nullable View convertView, @NonNull ViewGroup parent) {
        View custom=context.getLayoutInflater().inflate(resource,null);
        TextView txtName=custom.findViewById(R.id.txtName);
        TextView txtType=custom.findViewById(R.id.txtType);
        SmallAction smallAction=getItem(position);
        txtName.setText(smallAction.getName());
        txtType.setText(smallAction.getType()+"");
        return custom;
    }
}
